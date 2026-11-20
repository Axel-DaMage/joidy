"""
Obsidian webhook endpoints.

Receives external change notifications from Obsidian (or compatible
markdown editors) and synchronizes them with the database.

Authentication:
    If ``OBSIDIAN_WEBHOOK_SECRET`` is configured, requests must carry a
    matching ``X-Webhook-Secret`` header. The legacy ``?secret=`` query
    parameter still works for backward compatibility but is deprecated —
    it leaks via access/proxy logs — and logs a warning when used (#1288).
    When no secret is configured, the endpoint falls back to JWT auth so
    it is never left wide open.

Webhook payload format:
    POST /webhook/obsidian
    X-Webhook-Secret: <secret>
    {
        "event": "create" | "update" | "delete",
        "path": "/vault/note.md",
        "content": "...",        # omitted on delete
        "mtime": 1234567890      # optional, Unix timestamp
    }
"""

import hmac
import logging
from datetime import UTC, datetime

from config import settings
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, field_validator
from services.auth_service import _connection_host, _effective_auth_password, _is_loopback, get_current_user_id
from services.sync_service import to_utc_naive
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

    If ``OBSIDIAN_WEBHOOK_SECRET`` is configured, the request must carry a
    matching ``X-Webhook-Secret`` header (preferred) or ``?secret=`` query
    param (deprecated, kept for backward compatibility). The comparison
    uses ``hmac.compare_digest`` to avoid timing oracles (#1288).

    When no secret is configured the endpoint falls back to JWT auth so it
    is never left wide open. In development without ``AUTH_PASSWORD`` the
    unauthenticated path applies to loopback clients only (#1282).
    """
    provided = request.headers.get("X-Webhook-Secret")
    if not provided:
        # An absent (or empty) header falls back to the deprecated ?secret=
        # query param for backward compatibility (#1288).
        if secret:
            logger.warning(
                "[webhook] secret sent via ?secret= query param — deprecated, "
                "use the X-Webhook-Secret header instead (#1288)"
            )
        provided = secret

    if settings.obsidian_webhook_secret:
        if not hmac.compare_digest(provided, settings.obsidian_webhook_secret):
            raise HTTPException(status_code=401, detail="Invalid webhook secret")
        return

    # No webhook secret configured — fall back to JWT auth. In development
    # without AUTH_PASSWORD the bypass applies to loopback clients only.
    if not _effective_auth_password() and _is_loopback(_connection_host(request)):
        return

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Webhook secret not configured. Set OBSIDIAN_WEBHOOK_SECRET or provide a Bearer token.",
        )
    token = auth_header.removeprefix("Bearer ").strip()
    if get_current_user_id(token) is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def _conflict_writes_allowed(secret: str) -> bool:
    """Whether this request may write ``SyncState.conflict`` (fail-closed).

    ``conflict=True`` arms the ``keep_remote`` vault read in conflict
    resolution — forging it used to require nothing more than a JWT (or, in
    dev, no auth at all). Only requests authenticated by a *configured*
    ``OBSIDIAN_WEBHOOK_SECRET`` may set or clear the flag; with no secret
    configured every webhook request leaves it untouched (#1314). When the
    secret IS configured, ``_verify_access`` has already guaranteed the
    presented secret matches.
    """
    return bool(settings.obsidian_webhook_secret) and secret == settings.obsidian_webhook_secret


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
            allow_conflict_flag=_conflict_writes_allowed(secret),
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

    sync.remote_mtime = to_utc_naive(datetime.fromtimestamp(remote_mtime, tz=UTC)) if remote_mtime else None
    sync.last_synced_at = to_utc_naive(datetime.now(UTC))

    # Fail closed (#1314): the conflict flag may only be written when the
    # request carried a configured OBSIDIAN_WEBHOOK_SECRET — JWT-fallback and
    # dev-open callers get the mtime bookkeeping above but never arm or
    # disarm a conflict.
    if _conflict_writes_allowed(secret):
        local = to_utc_naive(sync.local_mtime)
        remote = to_utc_naive(sync.remote_mtime)
        if local is not None and remote is not None and local != remote:
            sync.conflict = True
        else:
            sync.conflict = False

    db.commit()

    return {"status": "ok", "note_id": note_id, "conflict": sync.conflict}
