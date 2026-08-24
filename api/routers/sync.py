"""
Sync conflict management endpoints.

Provides endpoints to list and resolve sync conflicts between
Joidy and external sources (e.g. Obsidian).
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from services.sync_service import list_conflicts, resolve_conflict
from sqlalchemy.orm import Session

from database import get_db
from models.note import Note
from models.sync_state import SyncState

router = APIRouter(prefix="/sync", tags=["sync"])


class ResolveConflictIn(BaseModel):
    resolution: str
    merged_content: str | None = None

    @field_validator("resolution")
    @classmethod
    def resolution_must_be_valid(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in ("keep_local", "keep_remote", "merge"):
            raise ValueError("resolution must be 'keep_local', 'keep_remote', or 'merge'")
        return v


@router.get("/conflicts")
def get_conflicts(db: Session = Depends(get_db)):
    """List all notes with unresolved sync conflicts."""
    conflicts = list_conflicts(db)
    return {"conflicts": conflicts, "count": len(conflicts)}


@router.post("/resolve/{note_id}")
def resolve_note_conflict(
    note_id: int,
    payload: ResolveConflictIn,
    db: Session = Depends(get_db),
):
    """Resolve a sync conflict for a specific note.

    - ``keep_local``: Discard remote changes, keep DB content.
    - ``keep_remote``: Read vault file and overwrite DB with its content.
    - ``merge``: Use ``merged_content`` as the new content for both.
    """
    if payload.resolution == "merge" and not payload.merged_content:
        raise HTTPException(
            status_code=400,
            detail="merged_content is required for merge resolution",
        )

    result = resolve_conflict(
        db,
        note_id=note_id,
        resolution=payload.resolution,
        merged_content=payload.merged_content,
    )

    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])

    return result


@router.get("/status")
def get_sync_status(db: Session = Depends(get_db)):
    """Return the current vault sync status (#73).

    Provides the last sync time, the number of pending conflicts, and the
    total number of notes synced from Obsidian. The frontend polls this on
    load to display a sync status indicator.
    """
    # Most recent successful sync across all notes.
    last_sync_row = (
        db.query(SyncState.last_synced_at)
        .filter(SyncState.last_synced_at.isnot(None))
        .order_by(SyncState.last_synced_at.desc())
        .first()
    )
    last_sync_time = None
    if last_sync_row and last_sync_row[0] is not None:
        last_sync_time = last_sync_row[0].isoformat() + "Z"

    # Pending (unresolved) conflicts.
    pending_conflicts = db.query(SyncState).filter(SyncState.conflict.is_(True)).count()

    # Total notes synced from Obsidian.
    total_synced = db.query(Note).filter(Note.source == "obsidian").count()

    return {
        "last_sync_time": last_sync_time,
        "pending_conflicts": pending_conflicts,
        "total_synced": total_synced,
        "server_time": datetime.now(timezone.utc).isoformat() + "Z",
    }
