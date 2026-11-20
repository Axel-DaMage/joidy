"""Gmail integration router (#42).

Dedicated Gmail API surface over the shared Google OAuth connection managed
by ``routers/integrations/google.py`` — every call proxies to
gmail.googleapis.com with the stored (auto-refreshed) access token. This
complements, not replaces, the n8n → ``/emails`` sync path (different
architecture, untouched).

Reads need ``gmail.readonly``; label mutations (archive/trash/unread) need
``gmail.modify``; sending needs ``gmail.send``/``gmail.modify``. Tokens
granted before the scope bump provably lacking a capability answer 403
``GmailReconsentRequired`` so the client can prompt a reconnect — same
pattern as contacts (#43) and calendar write-back (#1233).

Token transport (#1461): read endpoints honor an explicit access-token
override via the ``X-Google-Token`` header only — never a ``?token=`` query
param, where credentials would leak into logs (same hardening as
``X-Spotify-Token``/``X-Strava-Token``, #1372).
"""

import httpx
from database import get_db
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from services import gmail_service as gms
from services import google_token_service as gts
from services.auth_service import get_current_user
from sqlalchemy.orm import Session

router = APIRouter(prefix="/integrations/gmail", tags=["integrations"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class GmailAttachmentMetaOut(BaseModel):
    attachment_id: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    size: int | None = None
    part_id: str | None = None


class GmailMessageSummaryOut(BaseModel):
    id: str | None = None
    thread_id: str | None = None
    label_ids: list[str] = Field(default_factory=list)
    snippet: str | None = None
    internal_date: str | None = None  # ISO-8601 (Gmail sends epoch millis)
    size_estimate: int | None = None
    history_id: str | None = None


class GmailMessageOut(GmailMessageSummaryOut):
    headers: dict[str, str] = Field(default_factory=dict)
    body_text: str | None = None
    body_html: str | None = None
    body_truncated: bool = False
    attachments: list[GmailAttachmentMetaOut] = Field(default_factory=list)


class GmailMessageListOut(BaseModel):
    messages: list[GmailMessageSummaryOut] = Field(default_factory=list)
    next_page_token: str | None = None
    result_size_estimate: int | None = None


class GmailAttachmentDownloadOut(BaseModel):
    attachment_id: str
    size: int
    data_base64: str


class GmailAttachmentIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str | None = Field(default=None, max_length=255)
    data_base64: str = Field(min_length=1)


class GmailSendIn(BaseModel):
    to: str | None = Field(default=None, max_length=4000)
    cc: str | None = Field(default=None, max_length=4000)
    bcc: str | None = Field(default=None, max_length=4000)
    subject: str | None = Field(default=None, max_length=500)
    body: str | None = Field(default=None, max_length=500_000)
    body_html: str | None = Field(default=None, max_length=1_000_000)
    attachments: list[GmailAttachmentIn] = Field(default_factory=list, max_length=10)


class GmailSendOut(BaseModel):
    id: str | None = None
    thread_id: str | None = None
    label_ids: list[str] = Field(default_factory=list)


class GmailMessageActionOut(BaseModel):
    id: str | None = None
    thread_id: str | None = None
    label_ids: list[str] = Field(default_factory=list)


class GmailHistoryMessageRef(BaseModel):
    id: str | None = None
    thread_id: str | None = None
    label_ids: list[str] = Field(default_factory=list)


class GmailHistoryLabelChange(BaseModel):
    message_id: str | None = None
    label_ids: list[str] = Field(default_factory=list)


class GmailHistoryRecord(BaseModel):
    id: str | None = None
    messages_added: list[GmailHistoryMessageRef] = Field(default_factory=list)
    messages_deleted: list[GmailHistoryMessageRef] = Field(default_factory=list)
    labels_added: list[GmailHistoryLabelChange] = Field(default_factory=list)
    labels_removed: list[GmailHistoryLabelChange] = Field(default_factory=list)


class GmailHistoryOut(BaseModel):
    history_id: str | None = None
    next_page_token: str | None = None
    records: list[GmailHistoryRecord] = Field(default_factory=list)


class GmailWatchStateOut(BaseModel):
    topic_name: str | None = None
    history_id: str | None = None
    expiration: str | None = None
    registered_at: str | None = None


class GmailWatchStatusOut(BaseModel):
    configured: bool
    state: dict | None = None


class GmailWatchOut(GmailWatchStateOut):
    pass


class GmailStatusOut(BaseModel):
    connected: bool
    # None = unknown (legacy token row without a stored scope string).
    gmail_read: bool | None = None
    gmail_modify: bool | None = None
    gmail_send: bool | None = None
    watch: GmailWatchStatusOut


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _read_token(token: str | None, db: Session) -> str:
    """Resolve the access token for read calls: an explicit ``X-Google-Token``
    header wins, else the stored/auto-refreshed Google token (same semantics
    as google.py). The override arrives by header only — credentials never
    travel in the query string (#1461)."""
    if token:
        return token
    stored = await gts.get_valid_access_token(db)
    if not stored:
        raise HTTPException(status_code=401, detail="Google no está conectado")
    try:
        gms.require_capability(db, "read")
    except gms.GmailReconsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return stored


async def _scoped_token(db: Session, capability: str) -> str:
    """Resolve the token for mutating calls — stored token only, plus a
    proactive scope check so under-scoped grants fail before hitting Google."""
    stored = await gts.get_valid_access_token(db)
    if not stored:
        raise HTTPException(status_code=401, detail="Google no está conectado")
    try:
        gms.require_capability(db, capability)
    except gms.GmailReconsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return stored


def _parse_label_ids(value: str | None) -> list[str] | None:
    """``label_ids=INBOX,SENT`` → validated list (None when unset)."""
    if not value:
        return None
    return gms.validate_label_ids([part for part in value.split(",") if part.strip()])


def _google_error_reasons(exc: httpx.HTTPStatusError) -> set:
    """Extract google.rpc error reasons (insufficientPermissions, ...) if present."""
    try:
        body = exc.response.json()
    except Exception:
        return set()
    errors = body.get("error", {})
    if not isinstance(errors, dict):
        return set()
    return {e.get("reason") for e in errors.get("errors") or [] if isinstance(e, dict)}


def _google_http_error(exc: httpx.HTTPStatusError) -> HTTPException:
    """Map a Gmail API failure to an HTTP error without leaking internals."""
    status = exc.response.status_code
    if status == 401:
        return HTTPException(
            status_code=401,
            detail="Google token inválido o expirado — reconecta tu cuenta en Ajustes",
        )
    if status == 403 and "insufficientPermissions" in _google_error_reasons(exc):
        return HTTPException(
            status_code=403,
            detail="El token de Google no tiene permiso para Gmail — reconecta tu cuenta en Ajustes",
        )
    if status == 404:
        return HTTPException(status_code=404, detail="Recurso de Gmail no encontrado")
    if status == 429:
        return HTTPException(status_code=429, detail="Google rate limit excedido — reintenta más tarde")
    if 400 <= status < 500:
        return HTTPException(status_code=status, detail="Gmail API error")
    return HTTPException(status_code=502, detail="Gmail API error")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/status", response_model=GmailStatusOut)
async def gmail_status(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Connection state, per-capability scope flags and watch registration."""
    caps = gms.gmail_capabilities(db)
    return {
        "connected": gts.is_connected(db),
        "gmail_read": caps["read"],
        "gmail_modify": caps["modify"],
        "gmail_send": caps["send"],
        "watch": {"configured": gms.watch_configured(), "state": gms.get_watch_state(db)},
    }


@router.get("/messages", response_model=GmailMessageListOut)
async def list_gmail_messages(
    q: str | None = Query(default=None, max_length=2048, description="Gmail search syntax"),
    since: str | None = Query(default=None, max_length=64, description="Epoch or ISO-8601 lower bound"),
    label_ids: str | None = Query(default=None, max_length=1024, description="Comma-separated label ids"),
    max_results: int = Query(default=50, ge=1, le=500),
    page_token: str | None = Query(default=None, max_length=2048),
    google_token: str | None = Header(default=None, alias="X-Google-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List message summaries. ``q`` accepts Gmail search operators; ``since``
    is the polling-friendly incremental filter (maps to ``after:<epoch>``)."""
    access_token = await _read_token(google_token, db)
    try:
        return await gms.list_messages(
            access_token,
            q=q,
            since=since,
            label_ids=_parse_label_ids(label_ids),
            max_results=max_results,
            page_token=page_token,
        )
    except gms.GmailReconsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except gms.GmailValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise _google_http_error(exc) from exc


# Declared before the /{message_id} routes so "send" can never be captured
# as a message id on the POST verb.
@router.post("/messages/send", response_model=GmailSendOut)
async def send_gmail_message(
    body: GmailSendIn,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Compose and send an email (RFC822 built server-side; optional
    base64 attachments up to the configured caps)."""
    access_token = await _scoped_token(db, "send")
    try:
        return await gms.send_message(access_token, body.model_dump())
    except gms.GmailReconsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except gms.GmailValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise _google_http_error(exc) from exc


@router.get("/messages/{message_id}", response_model=GmailMessageOut)
async def get_gmail_message(
    message_id: str,
    google_token: str | None = Header(default=None, alias="X-Google-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Full message detail: headers, text/html bodies, attachment metadata."""
    access_token = await _read_token(google_token, db)
    try:
        return await gms.get_message(access_token, message_id)
    except gms.GmailReconsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except gms.GmailValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise _google_http_error(exc) from exc


@router.get("/messages/{message_id}/attachments/{attachment_id}", response_model=GmailAttachmentDownloadOut)
async def get_gmail_attachment(
    message_id: str,
    attachment_id: str,
    google_token: str | None = Header(default=None, alias="X-Google-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Download one attachment as standard base64 (JSON). Pair ``attachment_id``
    with the message's ``attachments[]`` metadata for filename/mime type."""
    access_token = await _read_token(google_token, db)
    try:
        return await gms.get_attachment(access_token, message_id, attachment_id)
    except gms.GmailReconsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except gms.GmailPayloadTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except gms.GmailValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise _google_http_error(exc) from exc


async def _modify_labels(db: Session, message_id: str, add: list[str], remove: list[str]):
    """Shared label-mutation path for archive/trash/untrash/read/unread."""
    access_token = await _scoped_token(db, "modify")
    try:
        return await gms.modify_labels(access_token, message_id, add=add, remove=remove)
    except gms.GmailReconsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except gms.GmailValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise _google_http_error(exc) from exc


@router.post("/messages/{message_id}/archive", response_model=GmailMessageActionOut)
async def archive_gmail_message(
    message_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Archive: remove the INBOX label."""
    return await _modify_labels(db, message_id, add=[], remove=[gms.LABEL_INBOX])


@router.post("/messages/{message_id}/trash", response_model=GmailMessageActionOut)
async def trash_gmail_message(
    message_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Move to trash: add TRASH, drop INBOX."""
    return await _modify_labels(db, message_id, add=[gms.LABEL_TRASH], remove=[gms.LABEL_INBOX])


@router.post("/messages/{message_id}/untrash", response_model=GmailMessageActionOut)
async def untrash_gmail_message(
    message_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Restore from trash: remove TRASH, re-add INBOX."""
    return await _modify_labels(db, message_id, add=[gms.LABEL_INBOX], remove=[gms.LABEL_TRASH])


@router.post("/messages/{message_id}/read", response_model=GmailMessageActionOut)
async def mark_gmail_message_read(
    message_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Mark as read: remove the UNREAD label."""
    return await _modify_labels(db, message_id, add=[], remove=[gms.LABEL_UNREAD])


@router.post("/messages/{message_id}/unread", response_model=GmailMessageActionOut)
async def mark_gmail_message_unread(
    message_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Mark as unread: add the UNREAD label."""
    return await _modify_labels(db, message_id, add=[gms.LABEL_UNREAD], remove=[])


# ---------------------------------------------------------------------------
# users.watch — Pub/Sub push (needs GOOGLE_GMAIL_PUBSUB_TOPIC) + history poll
# ---------------------------------------------------------------------------


@router.post("/watch", response_model=GmailWatchOut)
async def register_gmail_watch(
    label_ids: str | None = Query(default=None, max_length=1024, description="Comma-separated label filter"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Register Gmail push notifications on the configured Pub/Sub topic.

    503 when ``GOOGLE_GMAIL_PUBSUB_TOPIC`` is unset — the polling paths
    (``GET /messages?since=`` and ``GET /history``) remain available."""
    access_token = await _scoped_token(db, "read")
    try:
        return await gms.register_watch(db, access_token, label_ids=_parse_label_ids(label_ids))
    except gms.GmailWatchNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except gms.GmailReconsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except gms.GmailValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise _google_http_error(exc) from exc


@router.get("/watch", response_model=GmailWatchStatusOut)
async def gmail_watch_status(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Whether push is configured plus the last watch registration (if any)."""
    return {"configured": gms.watch_configured(), "state": gms.get_watch_state(db)}


@router.delete("/watch")
async def stop_gmail_watch(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Stop push notifications (users.stop) and clear the stored state."""
    access_token = await _scoped_token(db, "read")
    try:
        return await gms.stop_watch(db, access_token)
    except gms.GmailReconsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise _google_http_error(exc) from exc


@router.get("/history", response_model=GmailHistoryOut)
async def gmail_history(
    start_history_id: str = Query(..., min_length=1, max_length=32),
    page_token: str | None = Query(default=None, max_length=2048),
    max_results: int = Query(default=100, ge=1, le=500),
    label_id: str | None = Query(default=None, max_length=128),
    google_token: str | None = Header(default=None, alias="X-Google-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Incremental mailbox changes since ``start_history_id`` — the polling
    counterpart of users.watch for detecting new mail."""
    access_token = await _read_token(google_token, db)
    try:
        return await gms.get_history(
            access_token,
            start_history_id=start_history_id,
            page_token=page_token,
            max_results=max_results,
            label_id=label_id,
        )
    except gms.GmailReconsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except gms.GmailValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise _google_http_error(exc) from exc
