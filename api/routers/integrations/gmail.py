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

import html as html_module
import logging

import httpx
from database import get_db
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from models.email_account import PLACEHOLDER_EMAIL, PROVIDER_GMAIL, EmailAccount
from pydantic import BaseModel, Field
from services import email_account_service as eas
from services import email_sync_service as ess
from services import gmail_service as gms
from services import google_service as gs
from services import google_token_service as gts
from services import oauth_state
from services.auth_service import get_current_user
from sqlalchemy.orm import Session

router = APIRouter(prefix="/integrations/gmail", tags=["integrations"])

# Public sub-router mounted WITHOUT the router-level JWT dependency
# (``app.include_router(gmail.callback_router)`` — same pattern as
# ``github.webhook_router``): the OAuth ``/accounts/callback`` is a browser
# redirect and cannot carry an Authorization header. Its CSRF protection is
# the HMAC-signed ``state`` parameter verified inside the handler (#1280).
callback_router = APIRouter(prefix="/integrations/gmail", tags=["integrations"])

logger = logging.getLogger(__name__)


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
    # Connected per-account mailboxes (#1659) — serialized email_accounts rows.
    accounts: list[dict] = Field(default_factory=list)


class EmailAccountOut(BaseModel):
    """Serialized ``email_accounts`` row — credentials never leave the API."""

    id: int
    provider: str
    email_address: str
    display_name: str | None = None
    is_active: bool
    has_credentials: bool
    last_sync_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    capabilities: dict | None = None
    watch: dict | None = None


class EmailAccountPatchIn(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class GmailAuthUrl(BaseModel):
    url: str


class GmailAccountSyncOut(BaseModel):
    mode: str
    synced: int
    deleted: int = 0
    history_pages: int = 0
    account_id: int
    cursor: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _resolve_account(db: Session, user_id: int, account_id: int | None) -> EmailAccount | None:
    """Load and validate an account_id → gmail ``email_accounts`` row.

    ``__pending__`` addresses left by the migration are resolved through
    users.getProfile on first use (best-effort inside this call)."""
    if account_id is None:
        return None
    account = eas.get_account(db, user_id, account_id)
    if account is None or account.provider != PROVIDER_GMAIL or not account.is_active:
        raise HTTPException(status_code=404, detail="Cuenta de correo no encontrada")
    await eas.resolve_pending_profile(db, account)
    return account


async def _account_token(db: Session, account: EmailAccount, capability: str) -> str:
    """Access token from the account's own credentials (+ scope gate)."""
    token = await eas.get_account_access_token(db, account)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="La cuenta no está conectada — reconéctala en Ajustes",
        )
    try:
        eas.require_account_capability(account, capability)
    except gms.GmailReconsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return token


async def _read_token(token: str | None, db: Session, account: EmailAccount | None = None) -> str:
    """Resolve the access token for read calls: an explicit ``X-Google-Token``
    header wins, else the account's credentials (#1659), else the
    stored/auto-refreshed shared Google token (same semantics as google.py).
    The override arrives by header only — credentials never travel in the
    query string (#1461)."""
    if token:
        return token
    if account is not None:
        return await _account_token(db, account, "read")
    stored = await gts.get_valid_access_token(db)
    if not stored:
        raise HTTPException(status_code=401, detail="Google no está conectado")
    try:
        gms.require_capability(db, "read")
    except gms.GmailReconsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return stored


async def _scoped_token(db: Session, capability: str, account: EmailAccount | None = None) -> str:
    """Resolve the token for mutating calls — account credentials when scoped
    (#1659), else the shared stored token — plus a proactive scope check so
    under-scoped grants fail before hitting Google."""
    if account is not None:
        return await _account_token(db, account, capability)
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


def _gmail_accounts_payload(db: Session, user_id: int) -> list[dict]:
    """Serialized gmail email_accounts for status/account listings."""
    return [eas.serialize_account(a) for a in eas.list_accounts(db, user_id, provider=PROVIDER_GMAIL)]


@router.get("/status", response_model=GmailStatusOut)
async def gmail_status(
    account_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: int | None = Depends(get_current_user),
):
    """Connection state, per-capability scope flags and watch registration.

    With ``account_id`` the flags describe that account's own OAuth grant
    (#1659); otherwise they describe the shared Google connection. The
    ``accounts`` list always carries every connected gmail mailbox.
    """
    uid = user or 1
    account = await _resolve_account(db, uid, account_id)
    if account is not None:
        caps = eas.account_capabilities(account)
        return {
            "connected": bool(account.credentials),
            "gmail_read": caps["read"],
            "gmail_modify": caps["modify"],
            "gmail_send": caps["send"],
            "watch": {"configured": gms.watch_configured(), "state": gms.get_watch_state(db, account)},
            "accounts": _gmail_accounts_payload(db, uid),
        }
    caps = gms.gmail_capabilities(db)
    return {
        "connected": gts.is_connected(db),
        "gmail_read": caps["read"],
        "gmail_modify": caps["modify"],
        "gmail_send": caps["send"],
        "watch": {"configured": gms.watch_configured(), "state": gms.get_watch_state(db)},
        "accounts": _gmail_accounts_payload(db, uid),
    }


# ---------------------------------------------------------------------------
# Email accounts (#1659) — connect, list, patch, disconnect, sync
# ---------------------------------------------------------------------------


@router.get("/accounts", response_model=list[EmailAccountOut])
async def list_gmail_accounts(
    db: Session = Depends(get_db),
    user: int | None = Depends(get_current_user),
):
    """Connected gmail mailboxes — each carries its own credentials, sync
    cursor and watch state. Credentials are never serialized."""
    accounts = eas.list_accounts(db, user or 1, provider=PROVIDER_GMAIL)
    for account in accounts:
        await eas.resolve_pending_profile(db, account)
    return [eas.serialize_account(a) for a in accounts]


@router.get("/accounts/auth", response_model=GmailAuthUrl, dependencies=[Depends(get_current_user)])
def gmail_account_auth_url():
    """OAuth consent URL for connecting an ADDITIONAL gmail mailbox.

    Same Google consent screen and same registered ``google_redirect_uri``
    as the shared integration — the ``gmail`` state purpose is what routes
    the grant: ``/integrations/google/callback`` dispatches gmail-purpose
    states to ``handle_gmail_connect_callback``, where the tokens land on a
    new ``email_accounts`` row instead of the shared ``google_tokens`` row
    (#1659)."""
    try:
        state = oauth_state.generate_state("gmail")
        url = gs.get_auth_url(state=state)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"url": url}


@callback_router.get("/accounts/callback")
async def gmail_account_callback(
    code: str = "",
    error: str = "",
    state: str = "",
    db: Session = Depends(get_db),
):
    """Browser-redirect OAuth callback for an additional gmail mailbox —
    mounted on ``callback_router`` (no JWT): the redirect carries no
    Authorization header, protection is the signed ``state`` (#1280).

    In standard deployments the configured ``google_redirect_uri`` points at
    ``/integrations/google/callback`` and that handler dispatches here via
    ``handle_gmail_connect_callback``; this route covers deployments that
    also register this path as an extra redirect URI.
    """
    return await handle_gmail_connect_callback(code=code, error=error, state=state, db=db)


async def handle_gmail_connect_callback(code: str, error: str, state: str, db: Session) -> HTMLResponse:
    """Complete the additional-gmail-mailbox OAuth flow (#1659).

    Verifies the ``gmail``-purpose state, exchanges the code, resolves the
    mailbox address via users.getProfile and upserts the ``email_accounts``
    row with its own credential blob — re-consent on an existing address
    refreshes that row's grant. Called by ``/accounts/callback`` and by the
    shared ``/integrations/google/callback`` dispatch.

    The callback is unauthenticated (browser redirect); the account binds to
    the single-user id — same convention as the google callback storing the
    shared ``google_tokens`` row.
    """
    if error:
        return _account_callback_page(ok=False, message="Error de autorización con Google")
    if not code:
        return _account_callback_page(ok=False, message="Falta el código de autorización")
    if not oauth_state.verify_state(state, "gmail"):
        return _account_callback_page(ok=False, message="Estado OAuth inválido o expirado", status_code=403)

    try:
        tokens = await gs.exchange_code(code)
    except httpx.HTTPStatusError:
        return _account_callback_page(ok=False, message="Intercambio de token con Google falló")
    except RuntimeError:
        return _account_callback_page(ok=False, message="Google OAuth no está configurado")

    access_token = tokens.get("access_token", "")
    address = PLACEHOLDER_EMAIL
    profile: dict | None = None
    if access_token:
        try:
            profile = await gs.get_gmail_profile(access_token)
            address = str(profile.get("emailAddress") or "").strip() or PLACEHOLDER_EMAIL
        except Exception:  # noqa: BLE001 — placeholder resolves lazily later
            profile = None

    await eas.store_gmail_tokens(db, 1, address, tokens, profile=profile)
    return _account_callback_page(ok=True, message="Cuenta de Gmail conectada")


def _account_callback_page(ok: bool, message: str, status_code: int = 200) -> HTMLResponse:
    """Self-closing popup page — same pattern as the google OAuth callback."""
    icon = "OK" if ok else "ERROR"
    color = "#2e9e4f" if ok else "#c0392b"
    safe = html_module.escape(message or "", quote=True)
    page = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Joidy</title></head>
<body style="font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
<div style="text-align:center">
<p style="font-size:15px;color:{color};font-weight:600">{icon} — {safe}</p>
<p style="font-size:12px;color:#777">Puedes cerrar esta ventana.</p>
</div>
<script>setTimeout(function(){{ window.close(); }}, 1200);</script>
</body></html>"""
    return HTMLResponse(content=page, status_code=status_code)


@router.patch("/accounts/{account_id}", response_model=EmailAccountOut)
def patch_gmail_account(
    account_id: int,
    body: EmailAccountPatchIn,
    db: Session = Depends(get_db),
    user: int | None = Depends(get_current_user),
):
    """Rename or activate/deactivate a connected mailbox."""
    account = eas.get_account(db, user or 1, account_id)
    if account is None or account.provider != PROVIDER_GMAIL:
        raise HTTPException(status_code=404, detail="Cuenta de correo no encontrada")
    return eas.serialize_account(
        eas.update_account(db, account, display_name=body.display_name, is_active=body.is_active)
    )


@router.delete("/accounts/{account_id}", status_code=204)
async def disconnect_gmail_account(
    account_id: int,
    db: Session = Depends(get_db),
    user: int | None = Depends(get_current_user),
):
    """Disconnect one mailbox: drops the account row and its credentials.

    Synced messages keep their ``account`` label (account_id → NULL). An
    active users.watch registration is stopped best-effort first."""
    account = eas.get_account(db, user or 1, account_id)
    if account is None or account.provider != PROVIDER_GMAIL:
        raise HTTPException(status_code=404, detail="Cuenta de correo no encontrada")
    if account.watch_state:
        try:
            token = await eas.get_account_access_token(db, account)
            if token:
                await gms.request_stop_watch(token)
        except Exception as exc:  # noqa: BLE001 — disconnect must not fail on a dead watch
            logger.warning("[gmail] users.stop failed while disconnecting account %s: %s", account_id, exc)
    eas.delete_account(db, account)


@router.post("/accounts/{account_id}/sync", response_model=GmailAccountSyncOut)
async def sync_gmail_account(
    account_id: int,
    db: Session = Depends(get_db),
    user: int | None = Depends(get_current_user),
):
    """Pull this mailbox's mail into the unified ``/emails`` inbox — historyId
    incremental when a cursor exists, bounded backfill otherwise (#1659)."""
    uid = user or 1
    account = await _resolve_account(db, uid, account_id)
    try:
        return await ess.sync_account(db, uid, account)
    except ess.AccountNotConnected as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ess.ProviderNotSyncable as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except gms.GmailReconsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise _google_http_error(exc) from exc


@router.get("/messages", response_model=GmailMessageListOut)
async def list_gmail_messages(
    q: str | None = Query(default=None, max_length=2048, description="Gmail search syntax"),
    since: str | None = Query(default=None, max_length=64, description="Epoch or ISO-8601 lower bound"),
    label_ids: str | None = Query(default=None, max_length=1024, description="Comma-separated label ids"),
    max_results: int = Query(default=50, ge=1, le=500),
    page_token: str | None = Query(default=None, max_length=2048),
    account_id: int | None = Query(default=None, ge=1, description="email_accounts id (#1659)"),
    google_token: str | None = Header(default=None, alias="X-Google-Token"),
    db: Session = Depends(get_db),
    user: int | None = Depends(get_current_user),
):
    """List message summaries. ``q`` accepts Gmail search operators; ``since``
    is the polling-friendly incremental filter (maps to ``after:<epoch>``).
    ``account_id`` scopes the call to one connected mailbox's credentials."""
    account = await _resolve_account(db, user or 1, account_id)
    access_token = await _read_token(google_token, db, account)
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
    account_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: int | None = Depends(get_current_user),
):
    """Compose and send an email (RFC822 built server-side; optional
    base64 attachments up to the configured caps). ``account_id`` sends
    from that mailbox's own grant (#1659)."""
    account = await _resolve_account(db, user or 1, account_id)
    access_token = await _scoped_token(db, "send", account)
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
    account_id: int | None = Query(default=None, ge=1),
    google_token: str | None = Header(default=None, alias="X-Google-Token"),
    db: Session = Depends(get_db),
    user: int | None = Depends(get_current_user),
):
    """Full message detail: headers, text/html bodies, attachment metadata."""
    account = await _resolve_account(db, user or 1, account_id)
    access_token = await _read_token(google_token, db, account)
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
    account_id: int | None = Query(default=None, ge=1),
    google_token: str | None = Header(default=None, alias="X-Google-Token"),
    db: Session = Depends(get_db),
    user: int | None = Depends(get_current_user),
):
    """Download one attachment as standard base64 (JSON). Pair ``attachment_id``
    with the message's ``attachments[]`` metadata for filename/mime type."""
    account = await _resolve_account(db, user or 1, account_id)
    access_token = await _read_token(google_token, db, account)
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


async def _modify_labels(
    db: Session,
    message_id: str,
    add: list[str],
    remove: list[str],
    account_id: int | None = None,
    user_id: int | None = None,
):
    """Shared label-mutation path for archive/trash/untrash/read/unread."""
    account = await _resolve_account(db, user_id or 1, account_id)
    access_token = await _scoped_token(db, "modify", account)
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
    account_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: int | None = Depends(get_current_user),
):
    """Archive: remove the INBOX label."""
    return await _modify_labels(db, message_id, add=[], remove=[gms.LABEL_INBOX], account_id=account_id, user_id=user)


@router.post("/messages/{message_id}/trash", response_model=GmailMessageActionOut)
async def trash_gmail_message(
    message_id: str,
    account_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: int | None = Depends(get_current_user),
):
    """Move to trash: add TRASH, drop INBOX."""
    return await _modify_labels(
        db, message_id, add=[gms.LABEL_TRASH], remove=[gms.LABEL_INBOX], account_id=account_id, user_id=user
    )


@router.post("/messages/{message_id}/untrash", response_model=GmailMessageActionOut)
async def untrash_gmail_message(
    message_id: str,
    account_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: int | None = Depends(get_current_user),
):
    """Restore from trash: remove TRASH, re-add INBOX."""
    return await _modify_labels(
        db, message_id, add=[gms.LABEL_INBOX], remove=[gms.LABEL_TRASH], account_id=account_id, user_id=user
    )


@router.post("/messages/{message_id}/read", response_model=GmailMessageActionOut)
async def mark_gmail_message_read(
    message_id: str,
    account_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: int | None = Depends(get_current_user),
):
    """Mark as read: remove the UNREAD label."""
    return await _modify_labels(db, message_id, add=[], remove=[gms.LABEL_UNREAD], account_id=account_id, user_id=user)


@router.post("/messages/{message_id}/unread", response_model=GmailMessageActionOut)
async def mark_gmail_message_unread(
    message_id: str,
    account_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: int | None = Depends(get_current_user),
):
    """Mark as unread: add the UNREAD label."""
    return await _modify_labels(db, message_id, add=[gms.LABEL_UNREAD], remove=[], account_id=account_id, user_id=user)


# ---------------------------------------------------------------------------
# users.watch — Pub/Sub push (needs GOOGLE_GMAIL_PUBSUB_TOPIC) + history poll
# ---------------------------------------------------------------------------


@router.post("/watch", response_model=GmailWatchOut)
async def register_gmail_watch(
    label_ids: str | None = Query(default=None, max_length=1024, description="Comma-separated label filter"),
    account_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: int | None = Depends(get_current_user),
):
    """Register Gmail push notifications on the configured Pub/Sub topic —
    per account when ``account_id`` is given (#1659): the registration and
    its historyId cursor land on that row's ``watch_state``/``sync_cursor``.

    503 when ``GOOGLE_GMAIL_PUBSUB_TOPIC`` is unset — the polling paths
    (``GET /messages?since=`` and ``GET /history``) remain available."""
    account = await _resolve_account(db, user or 1, account_id)
    access_token = await _scoped_token(db, "read", account)
    try:
        return await gms.register_watch(db, access_token, label_ids=_parse_label_ids(label_ids), account=account)
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
    account_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: int | None = Depends(get_current_user),
):
    """Whether push is configured plus the last watch registration (if any)."""
    account = await _resolve_account(db, user or 1, account_id)
    return {"configured": gms.watch_configured(), "state": gms.get_watch_state(db, account)}


@router.delete("/watch")
async def stop_gmail_watch(
    account_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: int | None = Depends(get_current_user),
):
    """Stop push notifications (users.stop) and clear the stored state."""
    account = await _resolve_account(db, user or 1, account_id)
    access_token = await _scoped_token(db, "read", account)
    try:
        return await gms.stop_watch(db, access_token, account=account)
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
    account_id: int | None = Query(default=None, ge=1),
    google_token: str | None = Header(default=None, alias="X-Google-Token"),
    db: Session = Depends(get_db),
    user: int | None = Depends(get_current_user),
):
    """Incremental mailbox changes since ``start_history_id`` — the polling
    counterpart of users.watch for detecting new mail."""
    account = await _resolve_account(db, user or 1, account_id)
    access_token = await _read_token(google_token, db, account)
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
