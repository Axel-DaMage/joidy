"""
Generic webhook sync service.

Processes create/update/delete events from external sources (Obsidian,
future integrations) and synchronizes them with the database.

Designed to be source-agnostic: the caller passes a ``source`` label
(e.g. "obsidian") and the service handles the DB operations using
existing note_service functions.
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from models.note import Note
from models.sync_state import SyncState
from services.note_service import (
    create_note,
    delete_note,
    note_to_response,
    update_note,
)
from services.sync_service import detect_conflict
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and body from markdown."""
    frontmatter = {}
    body = content
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            fm_text = content[3:end].strip()
            body = content[end + 3:].strip()
            for line in fm_text.splitlines():
                if ":" in line:
                    key, _, value = line.partition(":")
                    frontmatter[key.strip()] = value.strip()
    return frontmatter, body


def _extract_tags(content: str, frontmatter: dict) -> list[str]:
    """Extract tags from frontmatter and inline #tags."""
    tags = []
    if "tags" in frontmatter:
        raw = frontmatter["tags"].strip("[]")
        tags.extend([t.strip() for t in raw.split(",") if t.strip()])
    inline = re.findall(r"#([a-zA-Z][a-zA-Z0-9_-]+)", content)
    tags.extend(inline)
    return list(set(t.lower() for t in tags if t))


def _title_from_path(path: str) -> str:
    """Derive a note title from a file path."""
    return Path(path).stem.replace("-", " ").replace("_", " ").title()


def _find_note_by_path(db: Session, path: str) -> Note | None:
    """Find an existing note by its source_path."""
    return db.query(Note).filter(Note.source_path == path).first()


def _update_sync_state(
    db: Session,
    note_id: int,
    remote_mtime: datetime | None,
) -> SyncState:
    """Create or update the SyncState record for a note.

    Detects conflicts by comparing local_mtime vs remote_mtime.
    """
    sync = db.query(SyncState).filter(SyncState.note_id == note_id).first()
    if not sync:
        sync = SyncState(note_id=note_id)
        db.add(sync)

    sync.remote_mtime = remote_mtime
    sync.last_synced_at = datetime.now(timezone.utc)
    sync.conflict = detect_conflict(sync.local_mtime, remote_mtime)
    return sync


def process_webhook_event(
    db: Session,
    *,
    event: str,
    path: str,
    content: str | None = None,
    mtime: int | None = None,
    source: str = "obsidian",
) -> dict:
    """Process a single webhook event.

    Args:
        event: One of "create", "update", "delete".
        path: The file path relative to the vault root.
        content: The file content (required for create/update, ignored for delete).
        mtime: Optional remote modification time as Unix timestamp.
        source: The source label (e.g. "obsidian").

    Returns:
        A dict with status info: {"status", "note_id", "action", "conflict"}
    """
    event = event.lower().strip()
    if event not in ("create", "update", "delete"):
        raise ValueError(f"Unsupported event type: {event}")

    remote_mtime = (
        datetime.fromtimestamp(mtime, tz=timezone.utc) if mtime else None
    )

    if event == "delete":
        note = _find_note_by_path(db, path)
        if note is None:
            logger.info("[webhook] Delete event for unknown path: %s", path)
            return {"status": "ok", "note_id": None, "action": "noop", "conflict": False}

        note_id = note.id
        # Remove SyncState first to avoid FK constraint when note is deleted
        sync = db.query(SyncState).filter(SyncState.note_id == note_id).first()
        if sync:
            db.delete(sync)
        delete_note(db, note_id)
        logger.info("[webhook] Deleted note %d for path %s", note_id, path)
        return {"status": "ok", "note_id": note_id, "action": "deleted", "conflict": False}

    if content is None:
        raise ValueError(f"Content is required for {event} events")

    frontmatter, _ = _parse_frontmatter(content)
    title = frontmatter.get("title") or _title_from_path(path)
    tags = _extract_tags(content, frontmatter)

    existing = _find_note_by_path(db, path)

    if existing is not None:
        note, _ = update_note(
            db,
            existing.id,
            title=title,
            content=content,
            tags=tags,
            source=source,
            source_path=path,
            from_vault=True,
        )
        action = "updated"
    else:
        note, _ = create_note(
            db,
            title=title,
            content=content,
            tags=tags,
            source=source,
            source_path=path,
            from_vault=True,
        )
        action = "created"

    sync = _update_sync_state(db, note.id, remote_mtime)
    db.commit()

    logger.info("[webhook] %s note %d for path %s", action, note.id, path)
    return {
        "status": "ok",
        "note_id": note.id,
        "action": action,
        "conflict": sync.conflict,
    }
