"""Spotify integration router."""

from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from services import spotify_service as sp
from services.auth_service import get_current_user

router = APIRouter(prefix="/integrations/spotify", tags=["integrations"])


class SpotifyAuthUrl(BaseModel):
    url: str


@router.get("/auth", response_model=SpotifyAuthUrl)
async def get_spotify_auth_url():
    """Return the Spotify OAuth consent URL."""
    try:
        url = sp.get_auth_url()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"url": url}


@router.get("/callback")
async def spotify_oauth_callback(code: str = "", error: str = ""):
    """Handle the OAuth callback from Spotify."""
    if error:
        raise HTTPException(status_code=400, detail=f"Spotify OAuth error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

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
    token: str,
    limit: int = 20,
    user: dict = Depends(get_current_user),
):
    """List recently played Spotify tracks."""
    try:
        return await sp.get_recently_played(token, limit)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Spotify API error")


@router.get("/top-tracks")
async def get_spotify_top_tracks(
    token: str,
    limit: int = 20,
    user: dict = Depends(get_current_user),
):
    """List top Spotify tracks."""
    try:
        return await sp.get_top_tracks(token, limit)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Spotify API error")


@router.get("/playlists")
async def get_spotify_playlists(
    token: str,
    limit: int = 20,
    user: dict = Depends(get_current_user),
):
    """List Spotify playlists."""
    try:
        return await sp.get_playlists(token, limit)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Spotify API error")
