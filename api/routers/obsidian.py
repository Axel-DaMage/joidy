"""
Obsidian webhook endpoints.

Receives external change notifications from Obsidian (or compatible
markdown editors) and synchronizes them with the database.

Authentication:
    If ``OBSIDIAN_WEBHOOK_SECRET`` is configured, requests must include
    a matching ``secret`` query parameter. When no secret is configured,
    the endpoint falls back to JWT auth so it is never left wide open.

Webhook payload format:
    POST /webhook/obsidian?secret=<secret>
    {
        "event": "create" | "update" | "delete",
        "path": "/vault/note.md",
        "content": "...",        # omitted on delete
        "mtime": 1234567890      # optional, Unix timestamp
    }
"""

import logging
from datetime import datetime, timezone

from config import settings
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, field_validator
from services.auth_service import get_current_user_id, _effective_auth_password
from services.webhook_sync import process_webhook_event
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook/obsidian", tags=["obsidian"])


class ObsidianWebhookIn(BaseModel):
    """Payload for the Obsidian webhook."""

    event: str
    path: str
    content: str | None = None
    mtime: int | None = None

    @field_validator("event")
    @classmethod
    def event_must_be_valid(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in ("create", "update", "delete"):
            raise ValueError("event must be 'create', 'update', or 'delete'")
        return v


def _verify_access(request: Request, secret: str, db: Session) -> None:
    """Verify webhook access via shared secret or JWT fallback.

    If ``OBSIDIAN_WEBHOOK_SECRET`` is configured, requests must include
    a matching ``secret`` query parameter. When no secret is configured,
    the endpoint falls back to JWT auth so it is never left wide open
    in production. In development (no ``AUTH_PASSWORD``), the webhook
    is accessible without auth for convenience.
    """
    if settings.obsidian_webhook_secret:
        if secret != settings.obsidian_webhook_secret:
            raise HTTPException(status_code=401, detail="Invalid webhook secret")
        return

    # No webhook secret configured — fall back to JWT auth in production
    if not _effective_auth_password():
        return  # dev mode: no auth configured, allow access

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Webhook secret not configured. Set OBSIDIAN_WEBHOOK_SECRET or provide a Bearer token.",
        )
    token = auth_header.removeprefix("Bearer ").strip()
    if get_current_user_id(token) is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@router.post("")
def obsidian_webhook(
    payload: ObsidianWebhookIn,
    request: Request,
    secret: str = Query(default=""),
    db: Session = Depends(get_db),
):
    """Receive external Obsidian change notifications.

    Processes create/update/delete events and synchronizes the note
    in the database. Conflict detection is recorded in SyncState but
    conflict resolution is handled separately (issue #5).
    """
    _verify_access(request, secret, db)

    try:
        result = process_webhook_event(
            db,
            event=payload.event,
            path=payload.path,
            content=payload.content,
            mtime=payload.mtime,
            source="obsidian",
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("[webhook] Error processing event: %s", e)
        raise HTTPException(status_code=500, detail="Internal sync error")


@router.post("/legacy")
def obsidian_webhook_legacy(
    payload: dict,
    request: Request,
    secret: str = Query(default=""),
    db: Session = Depends(get_db),
):
    """Legacy webhook endpoint for backward compatibility.

    Accepts the old payload format (note_id, path, remote_mtime) and
    only records sync state without processing content.
    """
    _verify_access(request, secret, db)

    from models.sync_state import SyncState

    note_id = payload.get("note_id")
    remote_mtime = payload.get("remote_mtime")

    if not note_id:
        raise HTTPException(status_code=400, detail="note_id is required")

    sync = db.query(SyncState).filter(SyncState.note_id == note_id).first()
    if not sync:
        sync = SyncState(note_id=note_id)
        db.add(sync)

    sync.remote_mtime = (
        datetime.fromtimestamp(remote_mtime, tz=timezone.utc)
        if remote_mtime
        else None
    )
    sync.last_synced_at = datetime.now(timezone.utc)

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

    return {"status": "ok", "note_id": note_id, "conflict": sync.conflict}
