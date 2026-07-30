from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.sync_state import SyncState

router = APIRouter(prefix="/webhook/obsidian", tags=["obsidian"])


class ObsidianChangeIn(BaseModel):
    note_id: int
    path: str
    remote_mtime: int | None = None


@router.post("")
def obsidian_webhook(
    payload: ObsidianChangeIn,
    secret: str = "",
    db: Session = Depends(get_db),
):
    """Receive external Obsidian change notifications.

    This is the foundation for bidirectional WebSocket/push sync.
    It records the remote mtime and flags potential conflicts.
    """
    if settings.obsidian_webhook_secret and secret != settings.obsidian_webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    sync = db.query(SyncState).filter(SyncState.note_id == payload.note_id).first()
    if not sync:
        sync = SyncState(note_id=payload.note_id)
        db.add(sync)

    # TODO: compare local/remote mtime to detect conflicts (#73)
    sync.remote_mtime = (
        datetime.fromtimestamp(payload.remote_mtime, tz=timezone.utc)
        if payload.remote_mtime
        else None
    )
    sync.last_synced_at = datetime.now(timezone.utc)
    db.commit()

    return {"status": "ok", "note_id": payload.note_id}
