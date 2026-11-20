"""Strava integration router — OAuth, server-side tokens, activities, sync, webhook (#44).

Tokens are persisted encrypted in ``integration_tokens`` (provider
``"strava"``) by the OAuth callback — they are never returned to the
browser. Data endpoints resolve the access token server-side with
transparent refresh; the legacy ``X-Strava-Token`` header is still honored
as an explicit override for backward compatibility (#1328 kept it out of
query params).

Auth model mirrors the Google router: ``/callback`` and ``/webhook`` must
be reachable without a user JWT (browser redirect / Strava servers), so
they are public and protect themselves — the callback via the signed OAuth
``state``, the webhook via the configured verify token. Every other route
declares ``get_current_user`` itself; the router is included bare in
``main.py``.
"""

import hmac
import logging
from typing import Any

import httpx
from config import settings
from database import get_db
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from services import integration_token_service as its
from services import oauth_state
from services import strava_service as ss
from services.auth_service import get_current_user
from sqlalchemy.orm import Session

from routers.integrations import google as google_router

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/strava", tags=["integrations"])

PROVIDER = its.PROVIDER_STRAVA


class StravaAuthUrl(BaseModel):
    url: str


class StravaStatus(BaseModel):
    configured: bool
    connected: bool
    athlete: dict[str, Any] | None = None


class StravaSyncResult(BaseModel):
    fetched: int
    new: int
    xp_awarded: int
    weeks: list[str]
    bonus_weeks: list[str]


def _configured() -> bool:
    return bool(settings.strava_client_id and settings.strava_client_secret and settings.strava_redirect_uri)


async def _strava_token(db: Session, header_token: str | None) -> str:
    """Resolve the Strava access token: explicit ``X-Strava-Token`` header
    wins (legacy contract), else the stored token with transparent refresh."""
    if header_token:
        return header_token
    token = await its.get_valid_access_token(db, PROVIDER, ss.refresh_tokens)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Strava no está conectado o la sesión expiró — vuelve a conectar la integración",
        )
    return token


def _map_strava_error(exc: httpx.HTTPStatusError) -> HTTPException:
    """Translate upstream Strava failures without leaking tokens/details."""
    status = exc.response.status_code
    if status == 401:
        return HTTPException(
            status_code=401,
            detail="Strava token inválido o expirado — reconecta la integración",
        )
    if status == 429:
        return HTTPException(status_code=429, detail="Strava rate limit excedido — reintenta más tarde")
    if status == 404:
        return HTTPException(status_code=404, detail="Recurso de Strava no encontrado")
    if 400 <= status < 500:
        return HTTPException(status_code=status, detail="Strava API error")
    return HTTPException(status_code=502, detail="Strava API error")


# ---------------------------------------------------------------------------
# OAuth flow
# ---------------------------------------------------------------------------


@router.get("/auth", response_model=StravaAuthUrl, dependencies=[Depends(get_current_user)])
async def get_strava_auth_url():
    """Return the Strava OAuth consent URL with a signed CSRF ``state`` (#1328)."""
    try:
        state = oauth_state.generate_state("strava")
        url = ss.get_auth_url(state=state)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"url": url}


@router.get("/callback")
async def strava_oauth_callback(
    code: str = "",
    error: str = "",
    state: str = "",
    db: Session = Depends(get_db),
):
    """Handle the OAuth callback from Strava.

    Public route (bare browser redirect — no JWT). Tokens are exchanged and
    persisted encrypted server-side; the response is a self-closing popup
    page, never the tokens themselves (#44).
    """
    if error:
        return _callback_page(ok=False, message="Error de autorización con Strava")
    if not code:
        return _callback_page(ok=False, message="Falta el código de autorización")
    # CSRF gate (#1328): the state must be one this instance signed in /auth.
    # Verified before any token exchange so a forged callback cannot bind an
    # attacker's Strava account here.
    if not oauth_state.verify_state(state, "strava"):
        return _callback_page(ok=False, message="Estado OAuth inválido o expirado", status_code=403)

    try:
        tokens = await ss.exchange_code(code)
    except httpx.HTTPStatusError:
        # No surface raw provider/HTTP details to the browser (CodeQL py/stack-trace-exposure)
        return _callback_page(ok=False, message="Intercambio de token con Strava falló")
    except RuntimeError:
        return _callback_page(ok=False, message="Strava OAuth no está configurado")

    athlete = tokens.get("athlete") or {}
    athlete_id = athlete.get("id")
    its.store_tokens(
        db,
        PROVIDER,
        access_token=tokens.get("access_token", ""),
        refresh_token=tokens.get("refresh_token"),
        expires_in=tokens.get("expires_in") if isinstance(tokens.get("expires_in"), int) else None,
        expires_at=ss.expires_at_from(tokens),
        token_type=tokens.get("token_type", "Bearer"),
        account_id=str(athlete_id) if athlete_id is not None else None,
    )
    return _callback_page(ok=True, message="Strava conectado")


def _callback_page(ok: bool, message: str, status_code: int = 200) -> HTMLResponse:
    """Minimal self-closing page for the popup opened by the settings panel.

    Delegates to the Google router's helper — identical UX, single
    implementation (#42).
    """
    return google_router._callback_page(ok=ok, message=message, status_code=status_code)


# ---------------------------------------------------------------------------
# Status / connection management
# ---------------------------------------------------------------------------


@router.get("/status", response_model=StravaStatus)
async def strava_status(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Connection status: configured flag, stored tokens, athlete summary."""
    connected = its.is_connected(db, PROVIDER)
    athlete_summary: dict[str, Any] | None = None
    if connected:
        token = await its.get_valid_access_token(db, PROVIDER, ss.refresh_tokens)
        if token:
            try:
                athlete = await ss.get_athlete(token)
                athlete_summary = {
                    "id": athlete.get("id"),
                    "firstname": athlete.get("firstname"),
                    "lastname": athlete.get("lastname"),
                    "username": athlete.get("username"),
                    "profile": athlete.get("profile"),
                }
            except Exception:  # noqa: BLE001 — status must not fail on upstream errors
                logger.warning("[strava] status: athlete fetch failed", exc_info=True)
    return {"configured": _configured(), "connected": connected, "athlete": athlete_summary}


@router.post("/disconnect")
async def strava_disconnect(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Disconnect Strava — deauthorizes at Strava (best-effort) and deletes tokens."""
    row = its.get_stored_token(db, PROVIDER)
    if row and row.access_token:
        try:
            await ss.deauthorize(row.access_token)
        except Exception:  # noqa: BLE001 — local disconnect must succeed even if Strava is down
            logger.warning("[strava] deauthorize failed; clearing local tokens anyway", exc_info=True)
    its.clear_tokens(db, PROVIDER)
    return {"status": "disconnected"}


# ---------------------------------------------------------------------------
# Data endpoints
# ---------------------------------------------------------------------------


@router.get("/activities")
async def get_strava_activities(
    per_page: int = Query(default=30, ge=1, le=200),
    page: int = Query(default=1, ge=1),
    before: int | None = Query(default=None),
    after: int | None = Query(default=None),
    sport_type: str | None = Query(default=None, description="Case-insensitive sport filter (e.g. run, ride, swim)"),
    strava_token: str | None = Header(default=None, alias="X-Strava-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List recent Strava activities.

    Uses the stored token (auto-refreshed); ``X-Strava-Token`` remains as an
    explicit override — never a query param, where it would leak into access
    logs, browser history and Referer headers (#1328).
    """
    token = await _strava_token(db, strava_token)
    try:
        activities = await ss.list_activities(token, per_page=per_page, page=page, before=before, after=after)
    except httpx.HTTPStatusError as exc:
        raise _map_strava_error(exc) from exc
    if sport_type:
        activities = [a for a in activities if ss.matches_sport_type(a, sport_type)]
    return activities


@router.get("/activities/{activity_id}")
async def get_strava_activity(
    activity_id: int,
    strava_token: str | None = Header(default=None, alias="X-Strava-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get a single activity's full detail (map, laps/splits, elevation, …)."""
    token = await _strava_token(db, strava_token)
    try:
        return await ss.get_activity(token, activity_id)
    except httpx.HTTPStatusError as exc:
        raise _map_strava_error(exc) from exc


@router.get("/activities/{activity_id}/streams")
async def get_strava_activity_streams(
    activity_id: int,
    keys: str = Query(default=ss.DEFAULT_STREAM_KEYS, description="Comma-separated stream keys"),
    strava_token: str | None = Header(default=None, alias="X-Strava-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get time-series streams (time, latlng, altitude, heartrate, …) for the
    activity detail view — map route + elevation chart."""
    token = await _strava_token(db, strava_token)
    try:
        return await ss.get_activity_streams(token, activity_id, keys=keys)
    except httpx.HTTPStatusError as exc:
        raise _map_strava_error(exc) from exc


@router.get("/athlete")
async def get_strava_athlete(
    strava_token: str | None = Header(default=None, alias="X-Strava-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get the authenticated Strava athlete profile."""
    token = await _strava_token(db, strava_token)
    try:
        return await ss.get_athlete(token)
    except httpx.HTTPStatusError as exc:
        raise _map_strava_error(exc) from exc


@router.get("/stats")
async def get_strava_stats(
    strava_token: str | None = Header(default=None, alias="X-Strava-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get athlete stats: recent totals, year-to-date and all-time."""
    token = await _strava_token(db, strava_token)
    try:
        stored = its.get_stored_token(db, PROVIDER)
        return await ss.get_stats(token, athlete_id=stored.account_id if stored else None)
    except httpx.HTTPStatusError as exc:
        raise _map_strava_error(exc) from exc


@router.get("/routes")
async def get_strava_routes(
    per_page: int = Query(default=30, ge=1, le=200),
    page: int = Query(default=1, ge=1),
    strava_token: str | None = Header(default=None, alias="X-Strava-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List the athlete's saved routes."""
    token = await _strava_token(db, strava_token)
    try:
        return await ss.list_routes(token, per_page=per_page, page=page)
    except httpx.HTTPStatusError as exc:
        raise _map_strava_error(exc) from exc


# ---------------------------------------------------------------------------
# Sync + gamification
# ---------------------------------------------------------------------------


@router.post("/sync", response_model=StravaSyncResult)
async def strava_sync(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Pull recent activities and award XP idempotently.

    +5 XP per activity (``strava:activity:<id>`` dedup key) plus a weekly
    bonus per ISO week present in the window (``strava:week:<year>-W<ww>``).
    Replays/re-syncs can never double-award.
    """
    token = await _strava_token(db, None)
    try:
        result = await ss.sync_recent_activities(db, token)
    except httpx.HTTPStatusError as exc:
        raise _map_strava_error(exc) from exc
    return StravaSyncResult(**result)


# ---------------------------------------------------------------------------
# Webhook (public — verify-token protected, disabled unless configured)
# ---------------------------------------------------------------------------


def _webhook_enabled() -> bool:
    return bool(settings.strava_webhook_verify_token)


@router.get("/webhook")
async def strava_webhook_verify(request: Request):
    """Strava subscription handshake: echo ``hub.challenge`` only when
    ``hub.verify_token`` matches the configured secret (constant-time)."""
    if not _webhook_enabled():
        raise HTTPException(status_code=404, detail="Not found")

    params = request.query_params
    mode = params.get("hub.mode", "")
    verify_token = params.get("hub.verify_token", "")
    challenge = params.get("hub.challenge", "")

    expected = settings.strava_webhook_verify_token or ""
    if mode != "subscribe" or not challenge or not hmac.compare_digest(verify_token, expected):
        raise HTTPException(status_code=403, detail="Webhook verification failed")
    return JSONResponse({"hub.challenge": challenge})


@router.post("/webhook")
async def strava_webhook_event(request: Request, db: Session = Depends(get_db)):
    """Receive Strava activity events and award XP idempotently.

    Strava push events carry no signature — protection is the subscription
    itself (created with the verify token) plus the ``owner_id`` check
    against the connected athlete. Always answers 200 for ignorable events
    so Strava does not retry deliveries we already handled.
    """
    if not _webhook_enabled():
        raise HTTPException(status_code=404, detail="Not found")

    try:
        event = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from None
    if not isinstance(event, dict):
        raise HTTPException(status_code=400, detail="Invalid webhook payload")

    if event.get("object_type") != "activity" or event.get("aspect_type") != "create":
        return {"status": "ignored", "reason": "unsupported_event"}

    object_id = event.get("object_id")
    if object_id is None:
        return {"status": "ignored", "reason": "missing_object_id"}
    try:
        activity_id = int(object_id)
    except (TypeError, ValueError):
        return {"status": "ignored", "reason": "invalid_object_id"}

    stored = its.get_stored_token(db, PROVIDER)
    if not ss.webhook_owner_matches(stored.account_id if stored else None, event.get("owner_id")):
        return {"status": "ignored", "reason": "owner_mismatch"}

    token = await its.get_valid_access_token(db, PROVIDER, ss.refresh_tokens)
    if not token:
        return {"status": "ignored", "reason": "not_connected"}

    try:
        activity = await ss.get_activity(token, activity_id)
    except httpx.HTTPStatusError as exc:
        # Gone/private/revoked — retrying won't help; ack so Strava stops.
        if exc.response.status_code in (401, 403, 404):
            return {"status": "ignored", "reason": "activity_unavailable"}
        raise

    result = ss.award_single_activity(db, activity)
    return {"status": "ok", **result}
