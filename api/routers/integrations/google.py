"""Google Calendar, Tasks, Gmail and Contacts integration router.

Provides OAuth flow, token persistence, status, and data endpoints.
The callback persists the refresh token (encrypted) so users stay
connected across restarts and returns a tiny HTML page that closes
the popup window (#42 — one-click setup from Settings, GitHub-style).
"""

import html as html_module

import httpx
from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from services import google_service as gs
from services import google_token_service as gts
from services.auth_service import get_current_user
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
async def get_google_auth_url():
    """Return the Google OAuth consent URL."""
    try:
        url = gs.get_auth_url()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"url": url}


@router.get("/callback")
async def google_oauth_callback(code: str = "", error: str = "", db: Session = Depends(get_db)):
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


def _callback_page(ok: bool, message: str) -> HTMLResponse:
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
    return HTMLResponse(content=page, status_code=200)


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
async def google_status(db: Session = Depends(get_db)):
    """Check if Google integration is connected."""
    connected = gts.is_connected(db)
    return {"connected": connected}


@router.post("/disconnect")
async def google_disconnect(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Disconnect Google integration — removes stored tokens."""
    gts.clear_tokens(db)
    return {"status": "disconnected"}


@router.get("/calendars")
async def get_google_calendars(
    token: str | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List Google Calendars. Uses the stored token if `token` is not provided."""
    try:
        return await gs.list_calendars(await _access_token(token, db))
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Google API error")


@router.get("/calendars/{calendar_id}/events")
async def get_google_calendar_events(
    calendar_id: str,
    token: str | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List events from a Google Calendar. Uses the stored token if `token` is not provided."""
    try:
        return await gs.list_events(await _access_token(token, db), calendar_id)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Google API error")


@router.get("/tasks")
async def get_google_task_lists(
    token: str | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List Google Tasks lists. Uses the stored token if `token` is not provided."""
    try:
        return await gs.list_task_lists(await _access_token(token, db))
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Google API error")


@router.get("/gmail")
async def get_google_gmail_messages(
    token: str | None = None,
    max_results: int = 10,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List recent Gmail message headers. Uses the stored token if `token` is not provided."""
    try:
        return await gs.list_gmail_messages(await _access_token(token, db), max_results)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Google API error")


@router.get("/contacts")
async def get_google_contacts(
    token: str | None = None,
    page_size: int = 50,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List Google Contacts. Uses the stored token if `token` is not provided."""
    try:
        return await gs.list_contacts(await _access_token(token, db), page_size)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Google API error")


async def _access_token(token: str | None, db: Session) -> str:
    """Resolve the access token: explicit `token` wins, else stored/refreshed."""
    if token:
        return token
    stored = await gts.get_valid_access_token(db)
    if not stored:
        raise HTTPException(status_code=401, detail="Google no está conectado")
    return stored
