"""Spotify integration router — OAuth, server-side tokens, playback (#45).

Tokens are persisted encrypted in ``integration_tokens`` (provider
``"spotify"``) by the OAuth callback — they are never returned to the
browser. Data endpoints resolve the access token server-side with
transparent refresh; the legacy ``X-Spotify-Token`` header is still honored
as an explicit override (the scaffold contract, kept for backward
compatibility — never a query param, where it would leak into logs).

Auth model mirrors the Strava/Google routers: ``/callback`` must be
reachable without a user JWT (bare browser redirect from
accounts.spotify.com), so it is public and protects itself via the signed
OAuth ``state``. Every other route declares ``get_current_user`` itself;
the router is included bare in ``main.py``.

Playback control (``/play``, ``/pause``, ``/next``, ``/previous``) requires
a Spotify Premium account — free accounts get 403/404 from Spotify, mapped
to clear errors by ``_map_spotify_error``.
"""

import logging
from collections.abc import Awaitable
from typing import Any

import httpx
from config import settings
from database import get_db
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from services import integration_token_service as its
from services import oauth_state
from services import spotify_service as ss
from services.auth_service import get_current_user
from sqlalchemy.orm import Session

from routers.integrations import google as google_router

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/spotify", tags=["integrations"])

PROVIDER = its.PROVIDER_SPOTIFY


class SpotifyAuthUrl(BaseModel):
    url: str


class SpotifyStatus(BaseModel):
    configured: bool
    connected: bool
    account: dict[str, Any] | None = None


class SpotifyPlayRequest(BaseModel):
    """Body for ``PUT /play`` — mirrors Spotify's ``/me/player/play`` payload.

    ``context_uri`` (``spotify:album:…`` / ``spotify:playlist:…`` /
    ``spotify:artist:…``) plays a whole context; ``uris`` plays an explicit
    track list. ``offset_position``/``offset_uri`` select the starting item
    inside the context; ``position_ms`` seeks within the track.
    """

    device_id: str | None = None
    context_uri: str | None = None
    uris: list[str] | None = None
    offset_position: int | None = Field(default=None, ge=0)
    offset_uri: str | None = None
    position_ms: int | None = Field(default=None, ge=0)


class SpotifyPlaybackControlResponse(BaseModel):
    status: str


class SpotifyDisconnectResponse(BaseModel):
    status: str
    manage_apps_url: str


def _configured() -> bool:
    return bool(settings.spotify_client_id and settings.spotify_client_secret and settings.spotify_redirect_uri)


async def _spotify_token(db: Session, header_token: str | None) -> str:
    """Resolve the Spotify access token: explicit ``X-Spotify-Token`` header
    wins (legacy contract), else the stored token with transparent refresh."""
    if header_token:
        return header_token
    token = await its.get_valid_access_token(db, PROVIDER, ss.refresh_tokens)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Spotify no está conectado o la sesión expiró — vuelve a conectar la integración",
        )
    return token


def _map_spotify_error(exc: httpx.HTTPStatusError) -> HTTPException:
    """Translate upstream Spotify failures without leaking tokens/details.

    Premium gating: playback control on a free account comes back as 403
    ("Premium required") and a missing active device as 404 — surfaced with
    actionable messages instead of a bare passthrough.
    """
    status = exc.response.status_code
    if status == 401:
        return HTTPException(
            status_code=401,
            detail="Spotify token inválido o expirado — reconecta la integración",
        )
    if status == 403:
        return HTTPException(
            status_code=403,
            detail="Spotify rechazó la acción — el control de reproducción requiere una cuenta Premium",
        )
    if status == 404:
        return HTTPException(
            status_code=404,
            detail="Recurso de Spotify no encontrado o no hay un dispositivo activo",
        )
    if status == 429:
        return HTTPException(status_code=429, detail="Spotify rate limit excedido — reintenta más tarde")
    if 400 <= status < 500:
        return HTTPException(status_code=status, detail="Spotify API error")
    return HTTPException(status_code=502, detail="Spotify API error")


async def _run[T](coro: Awaitable[T]) -> T:
    """Await a service call, mapping upstream HTTP errors uniformly."""
    try:
        return await coro
    except httpx.HTTPStatusError as exc:
        raise _map_spotify_error(exc) from exc


# ---------------------------------------------------------------------------
# OAuth flow
# ---------------------------------------------------------------------------


@router.get("/auth", response_model=SpotifyAuthUrl, dependencies=[Depends(get_current_user)])
async def get_spotify_auth_url():
    """Return the Spotify OAuth consent URL with a signed CSRF ``state`` (#1328)."""
    try:
        state = oauth_state.generate_state("spotify")
        url = ss.get_auth_url(state=state)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"url": url}


@router.get("/callback")
async def spotify_oauth_callback(
    code: str = "",
    error: str = "",
    state: str = "",
    db: Session = Depends(get_db),
):
    """Handle the OAuth callback from Spotify.

    Public route (bare browser redirect — no JWT). Tokens are exchanged and
    persisted encrypted server-side; the response is a self-closing popup
    page, never the tokens themselves (#45).
    """
    if error:
        return _callback_page(ok=False, message="Error de autorización con Spotify")
    if not code:
        return _callback_page(ok=False, message="Falta el código de autorización")
    # CSRF gate (#1328): the state must be one this instance signed in /auth.
    # Verified before any token exchange so a forged callback cannot bind an
    # attacker's Spotify account here.
    if not oauth_state.verify_state(state, "spotify"):
        return _callback_page(ok=False, message="Estado OAuth inválido o expirado", status_code=403)

    try:
        tokens = await ss.exchange_code(code)
    except httpx.HTTPStatusError:
        # No surface raw provider/HTTP details to the browser (CodeQL py/stack-trace-exposure)
        return _callback_page(ok=False, message="Intercambio de token con Spotify falló")
    except RuntimeError:
        return _callback_page(ok=False, message="Spotify OAuth no está configurado")

    access_token = tokens.get("access_token", "")
    # Best-effort profile fetch: stores the Spotify user id as ``account_id``
    # (status display/debugging). Never blocks the connect on failure.
    account_id = None
    try:
        profile = await ss.get_profile(access_token)
        if profile.get("id") is not None:
            account_id = str(profile["id"])
    except Exception:  # noqa: BLE001 — profile is cosmetic; tokens are already valid
        logger.warning("[spotify] profile fetch after OAuth failed", exc_info=True)

    its.store_tokens(
        db,
        PROVIDER,
        access_token=access_token,
        refresh_token=tokens.get("refresh_token"),
        expires_in=tokens.get("expires_in") if isinstance(tokens.get("expires_in"), int) else None,
        token_type=tokens.get("token_type", "Bearer"),
        scope=tokens.get("scope"),
        account_id=account_id,
    )
    return _callback_page(ok=True, message="Spotify conectado")


def _callback_page(ok: bool, message: str, status_code: int = 200):
    """Minimal self-closing page for the popup opened by the settings panel.

    Delegates to the Google router's helper — identical UX, single
    implementation (#42).
    """
    return google_router._callback_page(ok=ok, message=message, status_code=status_code)


# ---------------------------------------------------------------------------
# Status / connection management
# ---------------------------------------------------------------------------


@router.get("/status", response_model=SpotifyStatus)
async def spotify_status(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Connection status: configured flag, stored tokens, profile summary."""
    connected = its.is_connected(db, PROVIDER)
    account_summary: dict[str, Any] | None = None
    if connected:
        token = await its.get_valid_access_token(db, PROVIDER, ss.refresh_tokens)
        if token:
            try:
                profile = await ss.get_profile(token)
                account_summary = {
                    "id": profile.get("id"),
                    "display_name": profile.get("display_name"),
                    "email": profile.get("email"),
                }
            except Exception:  # noqa: BLE001 — status must not fail on upstream errors
                logger.warning("[spotify] status: profile fetch failed", exc_info=True)
    return {"configured": _configured(), "connected": connected, "account": account_summary}


@router.post("/disconnect", response_model=SpotifyDisconnectResponse)
async def spotify_disconnect(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Disconnect Spotify — deletes the stored tokens.

    Spotify exposes NO token-revocation endpoint (spotify/web-api#600):
    removing the row kills the refresh token, and any access token still
    valid self-expires within ~1h. Users can fully revoke the app at
    https://www.spotify.com/account/apps/ (``SPOTIFY_MANAGE_APPS_URL``).
    """
    its.clear_tokens(db, PROVIDER)
    return {"status": "disconnected", "manage_apps_url": ss.SPOTIFY_MANAGE_APPS_URL}


# ---------------------------------------------------------------------------
# Data endpoints
# ---------------------------------------------------------------------------


@router.get("/currently-playing")
async def get_spotify_currently_playing(
    spotify_token: str | None = Header(default=None, alias="X-Spotify-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Current playback state — track, progress, device, shuffle/repeat.

    Returns ``{"is_playing": false, ...}`` (200) when nothing is playing;
    Spotify's upstream 204 is normalized, never propagated.
    """
    token = await _spotify_token(db, spotify_token)
    return await _run(ss.get_playback_state(token))


@router.get("/recently-played")
async def get_spotify_recently_played(
    limit: int = Query(default=20, ge=1, le=ss.MAX_PAGE_LIMIT),
    spotify_token: str | None = Header(default=None, alias="X-Spotify-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Recently played tracks (``limit`` ≤ 50)."""
    token = await _spotify_token(db, spotify_token)
    return await _run(ss.get_recently_played(token, limit=limit))


@router.get("/top-artists")
async def get_spotify_top_artists(
    time_range: str = Query(default=ss.DEFAULT_TOP_TIME_RANGE, description="short_term | medium_term | long_term"),
    limit: int = Query(default=20, ge=1, le=ss.MAX_PAGE_LIMIT),
    spotify_token: str | None = Header(default=None, alias="X-Spotify-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Top artists for ``time_range`` (Spotify: last 4 weeks / 6 months / all time)."""
    token = await _spotify_token(db, spotify_token)
    return await _run(ss.get_top_artists(token, time_range=time_range, limit=limit))


@router.get("/top-tracks")
async def get_spotify_top_tracks(
    time_range: str = Query(default=ss.DEFAULT_TOP_TIME_RANGE, description="short_term | medium_term | long_term"),
    limit: int = Query(default=20, ge=1, le=ss.MAX_PAGE_LIMIT),
    spotify_token: str | None = Header(default=None, alias="X-Spotify-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Top tracks for ``time_range`` (backward-compatible with the scaffold:
    ``limit`` only still works, ``time_range`` defaults to ``medium_term``)."""
    token = await _spotify_token(db, spotify_token)
    return await _run(ss.get_top_tracks(token, time_range=time_range, limit=limit))


@router.get("/playlists")
async def get_spotify_playlists(
    limit: int = Query(default=20, ge=1, le=ss.MAX_PAGE_LIMIT),
    offset: int = Query(default=0, ge=0),
    spotify_token: str | None = Header(default=None, alias="X-Spotify-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """The user's playlists (``limit`` ≤ 50, ``offset`` for paging)."""
    token = await _spotify_token(db, spotify_token)
    return await _run(ss.get_playlists(token, limit=limit, offset=offset))


@router.get("/playlists/{playlist_id}")
async def get_spotify_playlist(
    playlist_id: str,
    spotify_token: str | None = Header(default=None, alias="X-Spotify-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Single playlist detail + its first page of tracks."""
    token = await _spotify_token(db, spotify_token)
    return await _run(ss.get_playlist(token, playlist_id))


# ---------------------------------------------------------------------------
# Playback control (Spotify Premium required)
# ---------------------------------------------------------------------------


@router.put("/play", response_model=SpotifyPlaybackControlResponse)
async def spotify_play(
    body: SpotifyPlayRequest | None = None,
    spotify_token: str | None = Header(default=None, alias="X-Spotify-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Resume/start playback — empty body plays on the active device."""
    token = await _spotify_token(db, spotify_token)
    play_body = body or SpotifyPlayRequest()
    await _run(
        ss.play(
            token,
            device_id=play_body.device_id,
            context_uri=play_body.context_uri,
            uris=play_body.uris,
            offset_position=play_body.offset_position,
            offset_uri=play_body.offset_uri,
            position_ms=play_body.position_ms,
        ),
    )
    return {"status": "ok"}


@router.put("/pause", response_model=SpotifyPlaybackControlResponse)
async def spotify_pause(
    device_id: str | None = Query(default=None),
    spotify_token: str | None = Header(default=None, alias="X-Spotify-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Pause playback on ``device_id`` (or the active device)."""
    token = await _spotify_token(db, spotify_token)
    await _run(ss.pause(token, device_id=device_id))
    return {"status": "ok"}


@router.post("/next", response_model=SpotifyPlaybackControlResponse)
async def spotify_next(
    device_id: str | None = Query(default=None),
    spotify_token: str | None = Header(default=None, alias="X-Spotify-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Skip to the next track."""
    token = await _spotify_token(db, spotify_token)
    await _run(ss.next_track(token, device_id=device_id))
    return {"status": "ok"}


@router.post("/previous", response_model=SpotifyPlaybackControlResponse)
async def spotify_previous(
    device_id: str | None = Query(default=None),
    spotify_token: str | None = Header(default=None, alias="X-Spotify-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Go back to the previous track."""
    token = await _spotify_token(db, spotify_token)
    await _run(ss.previous_track(token, device_id=device_id))
    return {"status": "ok"}
