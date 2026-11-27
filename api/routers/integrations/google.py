"""Google Calendar, Tasks, Gmail and Contacts integration router.

Provides OAuth flow, token persistence, status, and data endpoints.
The callback persists the refresh token (encrypted) so users stay
connected across restarts and returns a tiny HTML page that closes
the popup window (#42 — one-click setup from Settings, GitHub-style).

Token transport (#1461): data endpoints honor an explicit access-token
override via the ``X-Google-Token`` header only — never a ``?token=`` query
param, where credentials would leak into logs (same hardening as
``X-Spotify-Token``/``X-Strava-Token``, #1372).
"""

import html as html_module
from datetime import datetime

import httpx
from database import get_db
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from models.google_calendar_event import GoogleCalendarEvent
from pydantic import BaseModel, Field
from services import gmail_service as gms
from services import google_calendar_service as gcs
from services import google_service as gs
from services import google_token_service as gts
from services import oauth_state
from services.auth_service import get_current_user, get_current_user_or_internal
from sqlalchemy.orm import Session

router = APIRouter(prefix="/integrations/google", tags=["integrations"])


class GoogleAuthUrl(BaseModel):
    url: str


class GoogleTokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_in: int
    token_type: str
    scope: str | None = None


class GoogleConnectCallback(BaseModel):
    code: str
    scope: str | None = None


@router.get("/auth", response_model=GoogleAuthUrl, dependencies=[Depends(get_current_user)])
def get_google_auth_url():
    """Return the Google OAuth consent URL with a signed CSRF ``state`` (#1280)."""
    try:
        state = oauth_state.generate_state("google")
        url = gs.get_auth_url(state=state)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"url": url}


@router.get("/callback")
async def google_oauth_callback(
    code: str = "",
    error: str = "",
    state: str = "",
    db: Session = Depends(get_db),
):
    """Handle the OAuth callback from Google.

    This is hit by a browser redirect (no Bearer header available), so it must
    not require an authenticated user. It persists the tokens directly and
    returns a minimal HTML page that closes the popup the Settings panel opened,
    which then flips to "connected" via the status polling loop.
    """
    if error:
        return _callback_page(ok=False, message="Error de autorización con Google")
    if not code:
        return _callback_page(ok=False, message="Falta el código de autorización")
    # CSRF gate (#1280): the state must be one this instance signed in /auth.
    # Verified before any token exchange so a forged callback cannot bind an
    # attacker's Google account here.
    if not oauth_state.verify_state(state, "google"):
        return _callback_page(ok=False, message="Estado OAuth inválido o expirado", status_code=403)

    try:
        tokens = await gs.exchange_code(code)
    except httpx.HTTPStatusError:
        # No surface raw provider/HTTP details to the browser (CodeQL py/stack-trace-exposure)
        return _callback_page(ok=False, message="Intercambio de token con Google falló")
    except RuntimeError:
        return _callback_page(ok=False, message="Google OAuth no está configurado")

    gts.store_tokens(
        db,
        access_token=tokens.get("access_token", ""),
        refresh_token=tokens.get("refresh_token"),
        expires_in=tokens.get("expires_in", 3600),
        token_type=tokens.get("token_type", "Bearer"),
        scope=tokens.get("scope"),
    )
    return _callback_page(ok=True, message="Google conectado")


def _callback_page(ok: bool, message: str, status_code: int = 200) -> HTMLResponse:
    """Minimal self-closing page for the popup opened by the settings panel."""
    icon = "OK" if ok else "ERROR"
    color = "#2e9e4f" if ok else "#c0392b"
    # Standard-library escaping (incl. quotes) for the text-node interpolation.
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


@router.post("/connect")
async def google_connect(
    payload: GoogleConnectCallback,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Exchange OAuth code and persist tokens in the database.

    The refresh token is encrypted before storage.
    """
    try:
        tokens = await gs.exchange_code(payload.code)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Google token exchange failed")
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    gts.store_tokens(
        db,
        access_token=tokens.get("access_token", ""),
        refresh_token=tokens.get("refresh_token"),
        expires_in=tokens.get("expires_in", 3600),
        token_type=tokens.get("token_type", "Bearer"),
        scope=tokens.get("scope"),
    )

    return {"status": "connected", "scope": tokens.get("scope")}


@router.get("/status", dependencies=[Depends(get_current_user)])
def google_status(db: Session = Depends(get_db)):
    """Check if Google integration is connected."""
    connected = gts.is_connected(db)
    return {"connected": connected}


@router.post("/disconnect")
def google_disconnect(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Disconnect Google integration — removes stored tokens."""
    gts.clear_tokens(db)
    return {"status": "disconnected"}


@router.get("/calendars")
async def get_google_calendars(
    google_token: str | None = Header(default=None, alias="X-Google-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List Google Calendars. Uses the stored token unless ``X-Google-Token`` overrides it."""
    try:
        return await gs.list_calendars(await _access_token(google_token, db))
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Google API error")


@router.get("/calendars/{calendar_id}/events")
async def get_google_calendar_events(
    calendar_id: str,
    google_token: str | None = Header(default=None, alias="X-Google-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List events from a Google Calendar. Uses the stored token unless ``X-Google-Token`` overrides it."""
    try:
        return await gs.list_events(await _access_token(google_token, db), calendar_id)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Google API error")


@router.get("/tasks")
async def get_google_task_lists(
    google_token: str | None = Header(default=None, alias="X-Google-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List Google Tasks lists. Uses the stored token unless ``X-Google-Token`` overrides it."""
    try:
        return await gs.list_task_lists(await _access_token(google_token, db))
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Google API error")


@router.get("/gmail")
async def get_google_gmail_messages(
    google_token: str | None = Header(default=None, alias="X-Google-Token"),
    max_results: int = Query(default=10, ge=1, le=500),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List recent Gmail message summaries. Uses the stored token unless
    ``X-Google-Token`` overrides it. Bare id/threadId stubs are hydrated with
    real metadata fields — same fix as the dedicated gmail router (#1458)."""
    access_token = await _access_token(google_token, db)
    try:
        stubs = await gs.list_gmail_messages(access_token, max_results)
        return await gms.hydrate_message_stubs(access_token, [m for m in stubs if isinstance(m, dict)])
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Google API error")


@router.get("/contacts")
async def get_google_contacts(
    google_token: str | None = Header(default=None, alias="X-Google-Token"),
    page_size: int = 50,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List Google Contacts. Uses the stored token unless ``X-Google-Token`` overrides it."""
    try:
        return await gs.list_contacts(await _access_token(google_token, db), page_size)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Google API error")


# ---------------------------------------------------------------------------
# Calendar sync (#1134) — local cache of Google Calendar events
# ---------------------------------------------------------------------------


class GoogleCalendarEventOut(BaseModel):
    google_id: str
    calendar_id: str
    summary: str | None = None
    description: str | None = None
    location: str | None = None
    status: str
    all_day: bool
    start_at: datetime
    end_at: datetime | None = None
    html_link: str | None = None
    # Effective display color (#rrggbb): event colorId palette entry, else the
    # calendar's backgroundColor. None when the calendar color is unknown.
    color: str | None = None


class GoogleCalendarSyncResult(BaseModel):
    synced_at: str
    calendars: list[dict]


@router.get("/calendar/status")
def google_calendar_status(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Sync status: last run, cached calendars and event count."""
    status = gcs.get_sync_status(db)
    status["connected"] = gts.is_connected(db)
    return status


@router.post("/calendar/sync", response_model=GoogleCalendarSyncResult)
async def google_calendar_sync(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_or_internal),
):
    """Sync all selected Google Calendars into the local cache."""
    try:
        return await gcs.sync_all(db)
    except RuntimeError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Google API error")


@router.get("/calendar/events", response_model=list[GoogleCalendarEventOut])
def google_calendar_events(
    start: datetime | None = Query(default=None, description="ISO lower bound (inclusive)"),
    end: datetime | None = Query(default=None, description="ISO upper bound (inclusive)"),
    calendar_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Read cached calendar events. Served locally — no Google API call."""
    events: list[GoogleCalendarEvent] = gcs.get_cached_events(db, start, end, calendar_id)
    colors = gcs.effective_colors(db, events)
    return [
        GoogleCalendarEventOut(
            google_id=e.google_id,
            calendar_id=e.calendar_id,
            summary=e.summary,
            description=e.description,
            location=e.location,
            status=e.status,
            all_day=e.all_day,
            start_at=e.start_at,
            end_at=e.end_at,
            html_link=e.html_link,
            color=colors.get(e.id),
        )
        for e in events
    ]


async def _access_token(token: str | None, db: Session) -> str:
    """Resolve the access token: an explicit ``X-Google-Token`` header wins,
    else the stored/auto-refreshed token. The override arrives by header
    only — credentials never travel in the query string (#1461)."""
    if token:
        return token
    stored = await gts.get_valid_access_token(db)
    if not stored:
        raise HTTPException(status_code=401, detail="Google no está conectado")
    return stored


class GoogleEventWriteIn(BaseModel):
    summary: str = Field(min_length=1, max_length=500)
    start: dict
    end: dict
    description: str | None = None
    calendar_id: str = "primary"


class GoogleEventPatchIn(BaseModel):
    summary: str | None = Field(default=None, min_length=1, max_length=500)
    start: dict | None = None
    end: dict | None = None
    description: str | None = None


@router.post("/calendar/events")
async def google_calendar_create_event(
    body: GoogleEventWriteIn,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Create a Google Calendar event from joidy (write-back, #1233)."""
    token = await _access_token(None, db)
    try:
        created = await gcs.create_google_event(
            db, token, body.calendar_id, body.summary, body.start, body.end, body.description
        )
    except gcs.GoogleReconsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Google API error")
    return {
        "google_id": created.get("id"),
        "calendar_id": body.calendar_id,
        "summary": created.get("summary"),
        "start": created.get("start"),
        "end": created.get("end"),
    }


@router.patch("/calendar/events/{google_event_id}")
async def google_calendar_update_event(
    google_event_id: str,
    body: GoogleEventPatchIn,
    calendar_id: str = Query(default="primary"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Patch a Google Calendar event from joidy (write-back, #1233)."""
    token = await _access_token(None, db)
    patch = body.model_dump(exclude_unset=True, exclude_none=True)
    try:
        updated = await gcs.update_google_event(db, token, calendar_id, google_event_id, patch)
    except gcs.GoogleReconsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Google API error")
    return {
        "google_id": updated.get("id"),
        "calendar_id": calendar_id,
        "summary": updated.get("summary"),
        "start": updated.get("start"),
        "end": updated.get("end"),
    }


@router.delete("/calendar/events/{google_event_id}")
async def google_calendar_delete_event(
    google_event_id: str,
    calendar_id: str = Query(default="primary"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Delete a Google Calendar event from joidy (write-back, #1233)."""
    token = await _access_token(None, db)
    try:
        await gcs.delete_google_event(db, token, calendar_id, google_event_id)
    except gcs.GoogleReconsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Google API error")
    return {"status": "deleted", "google_id": google_event_id}
