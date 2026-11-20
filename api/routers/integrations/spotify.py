"""Spotify integration router."""

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from services import oauth_state
from services import spotify_service as sp
from services.auth_service import get_current_user

router = APIRouter(prefix="/integrations/spotify", tags=["integrations"])


class SpotifyAuthUrl(BaseModel):
    url: str


@router.get("/auth", response_model=SpotifyAuthUrl, dependencies=[Depends(get_current_user)])
async def get_spotify_auth_url():
    """Return the Spotify OAuth consent URL with a signed CSRF ``state`` (#1328)."""
    try:
        state = oauth_state.generate_state("spotify")
        url = sp.get_auth_url(state=state)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"url": url}


@router.get("/callback")
async def spotify_oauth_callback(code: str = "", error: str = "", state: str = ""):
    """Handle the OAuth callback from Spotify."""
    if error:
        raise HTTPException(status_code=400, detail=f"Spotify OAuth error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    # CSRF gate (#1328): the state must be one this instance signed in /auth.
    # Verified before any token exchange so a forged callback cannot bind an
    # attacker's Spotify account here.
    if not oauth_state.verify_state(state, "spotify"):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    try:
        tokens = await sp.exchange_code(code)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Spotify token exchange failed")
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "access_token": tokens.get("access_token", ""),
        "refresh_token": tokens.get("refresh_token"),
        "expires_in": tokens.get("expires_in", 0),
        "token_type": tokens.get("token_type", "Bearer"),
        "scope": tokens.get("scope"),
    }


@router.get("/recently-played")
async def get_spotify_recently_played(
    limit: int = 20,
    spotify_token: str = Header(alias="X-Spotify-Token"),
    user: dict = Depends(get_current_user),
):
    """List recently played Spotify tracks.

    The Spotify access token travels in the ``X-Spotify-Token`` header —
    never as a query param, where it would leak into access logs, browser
    history and Referer headers (#1328). ``Authorization`` is not reused
    because it already carries the app JWT consumed by ``get_current_user``.
    """
    try:
        return await sp.get_recently_played(spotify_token, limit)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Spotify API error")


@router.get("/top-tracks")
async def get_spotify_top_tracks(
    limit: int = 20,
    spotify_token: str = Header(alias="X-Spotify-Token"),
    user: dict = Depends(get_current_user),
):
    """List top Spotify tracks. Token via ``X-Spotify-Token`` header (#1328)."""
    try:
        return await sp.get_top_tracks(spotify_token, limit)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Spotify API error")


@router.get("/playlists")
async def get_spotify_playlists(
    limit: int = 20,
    spotify_token: str = Header(alias="X-Spotify-Token"),
    user: dict = Depends(get_current_user),
):
    """List Spotify playlists. Token via ``X-Spotify-Token`` header (#1328)."""
    try:
        return await sp.get_playlists(spotify_token, limit)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Spotify API error")
