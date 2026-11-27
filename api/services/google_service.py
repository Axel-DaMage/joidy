"""Google OAuth and Calendar/Tasks API helpers."""

from typing import Any

import httpx
from config import settings
from services.http_client import http_client

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 — OAuth endpoint URL, not a password
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
        # Gmail send/modify (#42): archive/trash/unread act on labels
        # (gmail.modify); messages.send needs gmail.send. Tokens granted
        # before this change keep read access; write endpoints answer 403
        # until the user reconnects — same re-consent pattern as contacts.
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.modify",
        # `contacts` (read+write) supersedes `contacts.readonly` — the
        # dedicated /integrations/contacts CRUD endpoints need write (#43).
        # Tokens granted before this change keep working for reads; write
        # endpoints answer 403 until the user reconnects.
        "https://www.googleapis.com/auth/contacts",
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


async def get_gmail_profile(token: str) -> dict[str, Any]:
    """users.getProfile — ``{emailAddress, historyId, messagesTotal, …}``.

    Used to resolve the real mailbox address after OAuth connect and to seed
    the initial historyId sync cursor for an email account (#1659)."""
    return await _request(token, f"{GOOGLE_GMAIL_API}/users/me/profile")


async def list_contacts(token: str, page_size: int = 50) -> list[dict[str, Any]]:
    """List the user's Google Contacts."""
    data = await _request(
        token,
        f"{GOOGLE_PEOPLE_API}/people/me/connections",
        params={"personFields": "names,emailAddresses", "pageSize": page_size},
    )
    return data.get("connections", [])


# ---------------------------------------------------------------------------
# People API — dedicated contacts surface (#43). Raw dict passthroughs; the
# business logic (normalization, scope checks, update merge) lives in
# services/google_contacts_service.py.
# ---------------------------------------------------------------------------


async def get_person(token: str, resource_name: str, person_fields: str) -> dict[str, Any]:
    """people.get — fetch one Person resource (``people/{id}``)."""
    return await _request(
        token,
        f"{GOOGLE_PEOPLE_API}/{resource_name}",
        params={"personFields": person_fields},
    )


async def search_contacts(token: str, query: str, read_mask: str, page_size: int = 30) -> dict[str, Any]:
    """people:searchContacts — prefix search over names/emails/phones/orgs.

    The endpoint is a GET with query params; ``pageSize`` is capped at 30 by
    Google and the response carries no pagination token.
    """
    return await _request(
        token,
        f"{GOOGLE_PEOPLE_API}/people:searchContacts",
        params={"query": query, "pageSize": min(page_size, 30), "readMask": read_mask},
    )


async def list_connections(
    token: str,
    person_fields: str,
    page_size: int = 100,
    page_token: str | None = None,
    sort_order: str | None = None,
) -> dict[str, Any]:
    """people.connections.list — one page of contacts (raw, keeps nextPageToken)."""
    params: dict[str, Any] = {"personFields": person_fields, "pageSize": page_size}
    if page_token:
        params["pageToken"] = page_token
    if sort_order:
        params["sortOrder"] = sort_order
    return await _request(token, f"{GOOGLE_PEOPLE_API}/people/me/connections", params)


async def create_contact(token: str, person: dict[str, Any], person_fields: str) -> dict[str, Any]:
    """people:createContact — returns the created Person resource."""
    return await _mutating_request(
        token,
        "POST",
        f"{GOOGLE_PEOPLE_API}/people:createContact",
        json=person,
        params={"personFields": person_fields},
    )


async def update_contact(
    token: str,
    resource_name: str,
    person: dict[str, Any],
    update_person_fields: str,
    person_fields: str,
) -> dict[str, Any]:
    """people:updateContact — PATCH; ``updatePersonFields`` is a required
    comma-separated field mask naming the top-level Person fields to replace.
    """
    return await _mutating_request(
        token,
        "PATCH",
        f"{GOOGLE_PEOPLE_API}/{resource_name}:updateContact",
        json=person,
        params={"updatePersonFields": update_person_fields, "personFields": person_fields},
    )


async def delete_contact(token: str, resource_name: str) -> None:
    """people:deleteContact."""
    await _mutating_request(token, "DELETE", f"{GOOGLE_PEOPLE_API}/{resource_name}:deleteContact")


async def list_contact_groups(token: str, page_size: int = 100, page_token: str | None = None) -> dict[str, Any]:
    """contactGroups.list — one page of the user's contact groups."""
    params: dict[str, Any] = {"pageSize": page_size}
    if page_token:
        params["pageToken"] = page_token
    return await _request(token, f"{GOOGLE_PEOPLE_API}/contactGroups", params)


async def get_contact_group(token: str, resource_name: str, max_members: int = 10000) -> dict[str, Any]:
    """contactGroups.get — includes ``memberResourceNames`` up to ``maxMembers``."""
    return await _request(
        token,
        f"{GOOGLE_PEOPLE_API}/{resource_name}",
        params={"maxMembers": max_members},
    )


# ---------------------------------------------------------------------------
# Gmail API — raw dict passthroughs for the dedicated /integrations/gmail
# surface (#42). Business logic (normalization, scope checks, RFC822 building,
# watch state) lives in services/gmail_service.py. All paths hang off
# users/me — message ids are validated upstream before reaching here.
# ---------------------------------------------------------------------------


async def list_gmail_messages_raw(token: str, params: dict[str, Any]) -> dict[str, Any]:
    """users.messages.list — one page of message stubs (id/threadId/snippet)."""
    return await _request(token, f"{GOOGLE_GMAIL_API}/users/me/messages", params)


async def get_gmail_message_raw(token: str, message_id: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """users.messages.get — full message resource (format=full by default)."""
    return await _request(
        token,
        f"{GOOGLE_GMAIL_API}/users/me/messages/{message_id}",
        params or {"format": "full"},
    )


async def modify_gmail_message_labels(
    token: str,
    message_id: str,
    add_label_ids: list[str],
    remove_label_ids: list[str],
) -> dict[str, Any]:
    """users.messages.modify — add/remove label ids (archive, trash, unread…)."""
    return await _mutating_request(
        token,
        "POST",
        f"{GOOGLE_GMAIL_API}/users/me/messages/{message_id}/modify",
        json={"addLabelIds": add_label_ids, "removeLabelIds": remove_label_ids},
    )


async def send_gmail_message(token: str, raw_rfc822: str) -> dict[str, Any]:
    """users.messages.send — ``raw`` is base64url-encoded RFC822 (no padding)."""
    return await _mutating_request(
        token,
        "POST",
        f"{GOOGLE_GMAIL_API}/users/me/messages/send",
        json={"raw": raw_rfc822},
    )


async def get_gmail_attachment(token: str, message_id: str, attachment_id: str) -> dict[str, Any]:
    """users.messages.attachments.get — returns ``{size, data}`` (base64url)."""
    return await _request(
        token,
        f"{GOOGLE_GMAIL_API}/users/me/messages/{message_id}/attachments/{attachment_id}",
    )


async def list_gmail_history(token: str, params: dict[str, Any]) -> dict[str, Any]:
    """users.history.list — incremental mailbox changes since ``startHistoryId``."""
    return await _request(token, f"{GOOGLE_GMAIL_API}/users/me/history", params)


async def watch_gmail_mailbox(token: str, topic_name: str, label_ids: list[str] | None = None) -> dict[str, Any]:
    """users.watch — register a Pub/Sub topic for push notifications."""
    body: dict[str, Any] = {"topicName": topic_name}
    if label_ids:
        body["labelIds"] = label_ids
    return await _mutating_request(token, "POST", f"{GOOGLE_GMAIL_API}/users/me/watch", json=body)


async def stop_gmail_watch(token: str) -> dict[str, Any]:
    """users.stop — stop push notifications for the mailbox."""
    return await _mutating_request(token, "POST", f"{GOOGLE_GMAIL_API}/users/me/stop")
