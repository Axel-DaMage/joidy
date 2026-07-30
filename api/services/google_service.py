"""Google OAuth and Calendar/Tasks API helpers."""

from typing import Any

import httpx
from config import settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"
GOOGLE_TASKS_API = "https://tasks.googleapis.com/tasks/v1"
GOOGLE_SCOPES = " ".join(
    [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/tasks.readonly",
    ]
)


def get_auth_url(state: str = "") -> str:
    """Build the Google OAuth consent URL."""
    if not settings.google_client_id or not settings.google_redirect_uri:
        raise RuntimeError("Google OAuth is not configured")

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
    }
    if state:
        params["state"] = state

    query = httpx.QueryParams(params)
    return f"{GOOGLE_AUTH_URL}?{query}"


async def exchange_code(code: str) -> dict[str, Any]:
    """Exchange an OAuth authorization code for tokens."""
    if not settings.google_client_secret or not settings.google_redirect_uri:
        raise RuntimeError("Google OAuth is not configured")

    payload = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.google_redirect_uri,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(GOOGLE_TOKEN_URL, data=payload)
        r.raise_for_status()
        return r.json()


async def _request(token: str, url: str, params: dict | None = None) -> Any:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params=params or {})
        r.raise_for_status()
        return r.json()


async def list_calendars(token: str) -> list[dict[str, Any]]:
    """List the user's Google Calendars."""
    data = await _request(token, f"{GOOGLE_CALENDAR_API}/users/me/calendarList")
    return data.get("items", [])


async def list_events(token: str, calendar_id: str = "primary") -> list[dict[str, Any]]:
    """List upcoming events from a calendar."""
    data = await _request(token, f"{GOOGLE_CALENDAR_API}/calendars/{calendar_id}/events")
    return data.get("items", [])


async def list_task_lists(token: str) -> list[dict[str, Any]]:
    """List the user's Google Tasks lists."""
    data = await _request(token, f"{GOOGLE_TASKS_API}/users/@me/lists")
    return data.get("items", [])
