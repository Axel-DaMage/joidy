"""Spotify OAuth and API helpers."""

from typing import Any

import httpx
from config import settings

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API = "https://api.spotify.com/v1"


def get_auth_url(state: str = "") -> str:
    """Build the Spotify OAuth consent URL."""
    if not settings.spotify_client_id or not settings.spotify_redirect_uri:
        raise RuntimeError("Spotify OAuth is not configured")

    params = {
        "client_id": settings.spotify_client_id,
        "redirect_uri": settings.spotify_redirect_uri,
        "response_type": "code",
        "scope": "user-read-recently-played user-read-playback-state user-top-read playlist-read-private",
    }
    if state:
        params["state"] = state

    query = httpx.QueryParams(params)
    return f"{SPOTIFY_AUTH_URL}?{query}"


async def exchange_code(code: str) -> dict[str, Any]:
    """Exchange an OAuth authorization code for tokens."""
    if not settings.spotify_client_secret or not settings.spotify_redirect_uri:
        raise RuntimeError("Spotify OAuth is not configured")

    auth = httpx.BasicAuth(settings.spotify_client_id, settings.spotify_client_secret)
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.spotify_redirect_uri,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(SPOTIFY_TOKEN_URL, data=payload, auth=auth)
        r.raise_for_status()
        return r.json()


async def _request(token: str, url: str, params: dict | None = None) -> Any:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params=params or {})
        r.raise_for_status()
        return r.json()


async def get_recently_played(token: str, limit: int = 20) -> list[dict[str, Any]]:
    """Get the user's recently played tracks."""
    data = await _request(
        token,
        f"{SPOTIFY_API}/me/player/recently-played",
        params={"limit": limit},
    )
    return data.get("items", [])


async def get_top_tracks(token: str, limit: int = 20) -> list[dict[str, Any]]:
    """Get the user's top tracks."""
    data = await _request(
        token,
        f"{SPOTIFY_API}/me/top/tracks",
        params={"limit": limit},
    )
    return data.get("items", [])


async def get_playlists(token: str, limit: int = 20) -> list[dict[str, Any]]:
    """Get the user's playlists."""
    data = await _request(
        token,
        f"{SPOTIFY_API}/me/playlists",
        params={"limit": limit},
    )
    return data.get("items", [])
