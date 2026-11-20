"""Google OAuth and Calendar/Tasks API helpers."""

from typing import Any

import httpx
from config import settings
from services.http_client import http_client

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"
GOOGLE_TASKS_API = "https://tasks.googleapis.com/tasks/v1"
GOOGLE_GMAIL_API = "https://gmail.googleapis.com/gmail/v1"
GOOGLE_PEOPLE_API = "https://people.googleapis.com/v1"
GOOGLE_SCOPES = " ".join(
    [
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/tasks.readonly",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/contacts.readonly",
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

    async with http_client(timeout=30.0) as client:
        r = await client.post(GOOGLE_TOKEN_URL, data=payload)
        r.raise_for_status()
        return r.json()


async def _request(token: str, url: str, params: dict | None = None) -> Any:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    async with http_client(timeout=30.0) as client:
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


async def list_events_raw(token: str, calendar_id: str, params: dict[str, Any]) -> dict[str, Any]:
    """Raw events.list call with custom params (pagination, syncToken, ...)."""
    return await _request(token, f"{GOOGLE_CALENDAR_API}/calendars/{calendar_id}/events", params)


async def _mutating_request(
    token: str,
    method: str,
    url: str,
    json: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    async with http_client(timeout=30.0) as client:
        r = await client.request(method, url, headers=headers, json=json, params=params or {})
        r.raise_for_status()
        if r.status_code == 204 or not r.content:
            return {}
        return r.json()


async def create_event(
    token: str, calendar_id: str, event: dict[str, Any], send_updates: str = "none"
) -> dict[str, Any]:
    """Create a Google Calendar event; returns the created event resource."""
    return await _mutating_request(
        token,
        "POST",
        f"{GOOGLE_CALENDAR_API}/calendars/{calendar_id}/events",
        json=event,
        params={"sendUpdates": send_updates},
    )


async def patch_event(
    token: str, calendar_id: str, google_event_id: str, patch: dict[str, Any], send_updates: str = "none"
) -> dict[str, Any]:
    """Patch a Google Calendar event; returns the updated event resource."""
    return await _mutating_request(
        token,
        "PATCH",
        f"{GOOGLE_CALENDAR_API}/calendars/{calendar_id}/events/{google_event_id}",
        json=patch,
        params={"sendUpdates": send_updates},
    )


async def delete_event(token: str, calendar_id: str, google_event_id: str, send_updates: str = "none") -> None:
    """Delete a Google Calendar event."""
    await _mutating_request(
        token,
        "DELETE",
        f"{GOOGLE_CALENDAR_API}/calendars/{calendar_id}/events/{google_event_id}",
        params={"sendUpdates": send_updates},
    )


async def list_task_lists(token: str) -> list[dict[str, Any]]:
    """List the user's Google Tasks lists."""
    data = await _request(token, f"{GOOGLE_TASKS_API}/users/@me/lists")
    return data.get("items", [])


async def list_gmail_messages(token: str, max_results: int = 10) -> list[dict[str, Any]]:
    """List recent Gmail message headers."""
    data = await _request(
        token,
        f"{GOOGLE_GMAIL_API}/users/me/messages",
        params={"maxResults": max_results},
    )
    return data.get("messages", [])


async def list_contacts(token: str, page_size: int = 50) -> list[dict[str, Any]]:
    """List the user's Google Contacts."""
    data = await _request(
        token,
        f"{GOOGLE_PEOPLE_API}/people/me/connections",
        params={"personFields": "names,emailAddresses", "pageSize": page_size},
    )
    return data.get("connections", [])
