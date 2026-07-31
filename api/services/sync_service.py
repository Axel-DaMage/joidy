"""
Sync conflict detection and resolution service.

Detects simultaneous changes to the same note from Joidy (local) and
Obsidian (remote), and provides resolution strategies.

Conflict detection is timestamp-based: if ``local_mtime`` and
``remote_mtime`` differ beyond a tolerance window, the note is flagged
as conflicted. Resolution options:
  - ``keep_local``: discard remote changes, keep DB content
  - ``keep_remote``: accept remote content, overwrite DB
  - ``merge``: manually provided content overrides both
"""

import logging
import os
from datetime import datetime, timezone
from typing import Literal

from config import settings
from models.note import Note
from models.sync_state import SyncState
from services.note_service import update_note
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

ConflictResolution = Literal["keep_local", "keep_remote", "merge"]

# Tolerance in seconds — mtimes within this window are considered equal
CONFLICT_TOLERANCE_SECONDS = 2


def detect_conflict(
    local_mtime: datetime | None,
    remote_mtime: datetime | None,
) -> bool:
    """Return True if local and remote mtimes differ beyond tolerance."""
    if local_mtime is None or remote_mtime is None:
        return False

    def _to_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    diff = abs((_to_utc(local_mtime) - _to_utc(remote_mtime)).total_seconds())
    return diff > CONFLICT_TOLERANCE_SECONDS


def list_conflicts(db: Session) -> list[dict]:
    """Return all notes with unresolved sync conflicts."""
    rows = (
        db.query(SyncState, Note)
        .join(Note, SyncState.note_id == Note.id)
        .filter(SyncState.conflict.is_(True))
        .all()
    )
    return [
        {
            "note_id": note.id,
            "title": note.title,
            "source_path": note.source_path,
            "local_mtime": sync.local_mtime.isoformat() + "Z" if sync.local_mtime else None,
            "remote_mtime": sync.remote_mtime.isoformat() + "Z" if sync.remote_mtime else None,
            "last_synced_at": sync.last_synced_at.isoformat() + "Z" if sync.last_synced_at else None,
        }
        for sync, note in rows
    ]


def resolve_conflict(
    db: Session,
    note_id: int,
    resolution: ConflictResolution,
    merged_content: str | None = None,
) -> dict:
    """Resolve a sync conflict for a note.

    Args:
        note_id: The ID of the conflicted note.
        resolution: How to resolve — keep_local, keep_remote, or merge.
        merged_content: Required for "merge" resolution. The manually
            merged content that overrides both local and remote.

    Returns:
        Dict with resolution status.
    """
    sync = db.query(SyncState).filter(SyncState.note_id == note_id).first()
    note = db.query(Note).filter(Note.id == note_id).first()

    if sync is None or note is None:
        return {"status": "error", "message": "Note or sync state not found"}

    if not sync.conflict:
        return {"status": "ok", "message": "No conflict to resolve", "note_id": note_id}

    if resolution == "keep_local":
        # Keep DB content as-is, just clear the conflict flag
        sync.conflict = False
        sync.last_synced_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("[sync] Resolved conflict for note %d: keep_local", note_id)

    elif resolution == "keep_remote":
        # Accept remote content — read from the vault file
        vault_path = settings.obsidian_vault_path
        if not vault_path or not note.source_path:
            return {"status": "error", "message": "Cannot read remote: vault path or source_path missing"}

        full_path = os.path.abspath(note.source_path)
        vault = os.path.abspath(vault_path)
        if not full_path.startswith(vault):
            return {"status": "error", "message": "Source path outside vault"}

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                remote_content = f.read()
        except Exception as e:
            return {"status": "error", "message": f"Cannot read vault file: {e}"}

        update_note(
            db,
            note_id,
            content=remote_content,
            from_vault=True,
            rebuild_derived_data=False,
        )
        sync.conflict = False
        sync.local_mtime = sync.remote_mtime
        sync.last_synced_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("[sync] Resolved conflict for note %d: keep_remote", note_id)

    elif resolution == "merge":
        if merged_content is None:
            return {"status": "error", "message": "merged_content is required for merge resolution"}

        update_note(
            db,
            note_id,
            content=merged_content,
            from_vault=False,
            rebuild_derived_data=False,
        )
        sync.conflict = False
        now = datetime.now(timezone.utc)
        sync.local_mtime = now
        sync.remote_mtime = now
        sync.last_synced_at = now
        db.commit()
        logger.info("[sync] Resolved conflict for note %d: merge", note_id)

    else:
        return {"status": "error", "message": f"Unknown resolution: {resolution}"}

    return {"status": "ok", "note_id": note_id, "resolution": resolution}


def update_local_mtime(db: Session, note_id: int) -> None:
    """Record the current time as local_mtime for a note.

    Called when a note is created or updated from Joidy (not from vault).
    """
    sync = db.query(SyncState).filter(SyncState.note_id == note_id).first()
    if not sync:
        sync = SyncState(note_id=note_id)
        db.add(sync)
    sync.local_mtime = datetime.now(timezone.utc)
    db.flush()
