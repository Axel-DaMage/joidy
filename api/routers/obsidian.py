from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.sync_state import SyncState
from services.auth_service import get_current_user

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
    _user_id: int = Depends(get_current_user),
):
    """Receive external Obsidian change notifications.

    This is the foundation for bidirectional WebSocket/push sync.
    It records the remote mtime and flags potential conflicts.

    Authentication: if ``OBSIDIAN_WEBHOOK_SECRET`` is configured, the
    request must include a matching ``secret`` query parameter. When no
    secret is configured, the endpoint falls back to JWT auth so it is
    never left wide open.
    """
    if settings.obsidian_webhook_secret:
        if secret != settings.obsidian_webhook_secret:
            raise HTTPException(status_code=401, detail="Invalid webhook secret")

    sync = db.query(SyncState).filter(SyncState.note_id == payload.note_id).first()
    if not sync:
        sync = SyncState(note_id=payload.note_id)
        db.add(sync)

    sync.remote_mtime = (
        datetime.fromtimestamp(payload.remote_mtime, tz=timezone.utc)
        if payload.remote_mtime
        else None
    )
    sync.last_synced_at = datetime.now(timezone.utc)

    # Conflict detection: compare UTC seconds since mtimes are stored
    # without timezone in some databases.
    def _to_naive_utc(dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    local = _to_naive_utc(sync.local_mtime)
    remote = _to_naive_utc(sync.remote_mtime)
    if local is not None and remote is not None and local != remote:
        sync.conflict = True
    else:
        sync.conflict = False

    db.commit()

    return {"status": "ok", "note_id": payload.note_id, "conflict": sync.conflict}
