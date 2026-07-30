"""Strava OAuth and API helpers."""

from typing import Any

import httpx
from config import settings

STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API = "https://www.strava.com/api/v3"


def get_auth_url(state: str = "") -> str:
    """Build the Strava OAuth consent URL."""
    if not settings.strava_client_id or not settings.strava_redirect_uri:
        raise RuntimeError("Strava OAuth is not configured")

    params = {
        "client_id": settings.strava_client_id,
        "redirect_uri": settings.strava_redirect_uri,
        "response_type": "code",
        "approval_prompt": "force",
        "scope": "read,activity:read",
    }
    if state:
        params["state"] = state

    query = httpx.QueryParams(params)
    return f"{STRAVA_AUTH_URL}?{query}"


async def exchange_code(code: str) -> dict[str, Any]:
    """Exchange an OAuth authorization code for tokens."""
    if not settings.strava_client_secret or not settings.strava_redirect_uri:
        raise RuntimeError("Strava OAuth is not configured")

    payload = {
        "client_id": settings.strava_client_id,
        "client_secret": settings.strava_client_secret,
        "code": code,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(STRAVA_TOKEN_URL, data=payload)
        r.raise_for_status()
        return r.json()


async def _request(token: str, url: str, params: dict | None = None) -> Any:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params=params or {})
        r.raise_for_status()
        return r.json()


async def list_activities(token: str, per_page: int = 30) -> list[dict[str, Any]]:
    """List the athlete's recent activities."""
    return await _request(
        token,
        f"{STRAVA_API}/athlete/activities",
        params={"per_page": per_page},
    )


async def get_athlete(token: str) -> dict[str, Any]:
    """Get the authenticated athlete's profile."""
    return await _request(token, f"{STRAVA_API}/athlete")
