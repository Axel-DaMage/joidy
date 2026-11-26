"""Google Calendar sync service (#1134).

Pulls events from the Google Calendar API into the local ``google_calendar_events``
cache using incremental sync (``syncToken``): the first run performs a full
sync over a rolling window, subsequent runs only transfer changes. Cancelled
events are removed from the cache. Requires only the ``calendar.readonly``
scope the OAuth flow already requests — no re-consent needed.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from models.google_calendar_event import GoogleCalendarEvent
from models.google_calendar_sync import GoogleCalendarSyncState
from services import google_service as gs
from services.google_token_service import get_valid_access_token
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# How far back the initial (full) sync reaches. Incremental syncs keep this
# window up to date forever after; events older than the window are dropped
# from the cache on full re-syncs.
SYNC_WINDOW_DAYS = 30

# Safety net so a lost sync_token never resyncs unbounded history.
INITIAL_MAX_RESULTS = 2500


def _parse_gcal_datetime(value: dict[str, Any] | None) -> tuple[datetime | None, bool]:
    """Parse a Google Calendar ``start``/``end`` object.

    Returns (datetime, all_day). ``dateTime`` is RFC3339 (tz-aware or UTC
    assumed); ``date`` is a plain calendar date (all-day event).
    """
    if not value:
        return None, False
    if "dateTime" in value:
        raw = value["dateTime"].replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            return None, False
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt, False
    if "date" in value:
        try:
            dt = datetime.fromisoformat(value["date"]).replace(tzinfo=UTC)
        except ValueError:
            return None, False
        return dt, True
    return None, False


def _upsert_event(
    db: Session,
    calendar_id: str,
    item: dict[str, Any],
    existing: dict[str, GoogleCalendarEvent] | None = None,
) -> bool:
    """Upsert one event item. Returns False if the item must be deleted.

    ``existing`` is an optional ``{google_id: row}`` map pre-loaded by the
    caller (``sync_calendar`` batch-loads the whole calendar in one SELECT —
    see #1521). When omitted (single-event write-back path), the row is
    looked up with one query as before. Rows added/deleted through this
    function keep the map in sync so duplicate ``google_id`` items in one
    batch behave exactly like repeated lookups did.
    """
    google_id = item.get("id")
    if not google_id:
        return False

    def _lookup() -> GoogleCalendarEvent | None:
        if existing is not None:
            return existing.get(google_id)
        return (
            db.query(GoogleCalendarEvent)
            .filter(
                GoogleCalendarEvent.user_id == 1,
                GoogleCalendarEvent.calendar_id == calendar_id,
                GoogleCalendarEvent.google_id == google_id,
            )
            .first()
        )

    if item.get("status") == "cancelled":
        deleted = _lookup()
        if deleted:
            if deleted in db.new:
                # Added earlier in this batch and still pending — delete()
                # rejects unpersisted instances, so flush first (write-only,
                # same net effect as the old autoflush-then-delete path).
                db.flush()
            db.delete(deleted)
            if existing is not None:
                existing.pop(google_id, None)
        return False

    start_at, all_day = _parse_gcal_datetime(item.get("start"))
    end_at, _ = _parse_gcal_datetime(item.get("end"))
    if start_at is None:
        logger.debug("[google] Skipping event %s without parsable start", google_id)
        return False

    row = _lookup()
    if not row:
        row = GoogleCalendarEvent(user_id=1, calendar_id=calendar_id, google_id=google_id)
        db.add(row)
        if existing is not None:
            existing[google_id] = row

    row.summary = item.get("summary")
    row.description = item.get("description")
    row.location = item.get("location")
    row.status = item.get("status", "confirmed")
    row.all_day = all_day
    row.start_at = start_at
    row.end_at = end_at
    row.html_link = item.get("htmlLink")
    return True


async def _list_all_pages(
    token: str, calendar_id: str, params: dict[str, Any]
) -> tuple[list[dict[str, Any]], str | None]:
    """Fetch all pages of events.list; return (items, nextSyncToken|None)."""
    items: list[dict[str, Any]] = []
    sync_token: str | None = None
    page_token: str | None = None

    while True:
        page_params = dict(params)
        if page_token:
            page_params["pageToken"] = page_token
        data = await gs.list_events_raw(token, calendar_id, page_params)
        items.extend(data.get("items", []))
        sync_token = data.get("nextSyncToken")
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return items, sync_token


async def sync_calendar(db: Session, token: str, calendar_id: str) -> dict[str, Any]:
    """Sync one calendar incrementally; falls back to a full sync on 410 GONE."""
    state = (
        db.query(GoogleCalendarSyncState)
        .filter(GoogleCalendarSyncState.user_id == 1, GoogleCalendarSyncState.calendar_id == calendar_id)
        .first()
    )

    params: dict[str, Any] = {"singleEvents": "true", "maxResults": "2500"}
    incremental = False
    if state and state.sync_token:
        params["syncToken"] = state.sync_token
        incremental = True
    else:
        params["timeMin"] = (datetime.now(UTC) - timedelta(days=SYNC_WINDOW_DAYS)).isoformat()
        params["orderBy"] = "startTime"

    try:
        items, sync_token = await _list_all_pages(token, calendar_id, params)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 410 and incremental:
            # Sync token expired (e.g. >30 days unused or policy change) —
            # drop it and force a full re-sync on the next attempt.
            logger.info("[google] Sync token for %s expired (410), full re-sync", calendar_id)
            if state:
                state.sync_token = None
                db.commit()
            return await sync_calendar(db, token, calendar_id)
        raise

    # Batch-load the calendar's cached rows once (#1521): a full sync returns
    # up to INITIAL_MAX_RESULTS items and per-item SELECTs were an N+1.
    existing: dict[str, GoogleCalendarEvent] = {
        row.google_id: row
        for row in db.query(GoogleCalendarEvent).filter(
            GoogleCalendarEvent.user_id == 1,
            GoogleCalendarEvent.calendar_id == calendar_id,
        )
    }

    synced = 0
    for item in items:
        if _upsert_event(db, calendar_id, item, existing):
            synced += 1

    if not state:
        state = GoogleCalendarSyncState(user_id=1, calendar_id=calendar_id)
        db.add(state)
    state.sync_token = sync_token
    state.last_synced_at = datetime.now(UTC)
    state.last_error = None

    # A complete full sync replaces the calendar's cache: drop events that
    # Google no longer returns (fell out of the window or removed remotely).
    # Incremental syncs never prune — Google reports deletions explicitly.
    if not incremental and sync_token:
        returned_ids = {item.get("id") for item in items}
        # ``existing`` already mirrors every live row for this calendar after
        # the upsert loop, so orphan detection needs no extra query.
        for google_id, orphan in list(existing.items()):
            if google_id not in returned_ids:
                db.delete(orphan)

    db.commit()

    return {
        "calendar_id": calendar_id,
        "synced": synced,
        "deleted": len(items) - synced,
        "incremental": incremental,
    }


def _selectable_calendars(calendars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter the calendarList down to calendars worth syncing."""
    selected = []
    for cal in calendars:
        if cal.get("deleted") or cal.get("id") is None:
            continue
        # `selected` is None for the primary calendar; explicit False = unchecked.
        if cal.get("selected") is False and not cal.get("primary"):
            continue
        if cal.get("accessRole") not in (None, "reader", "writer", "owner", "freeBusyReader"):
            continue
        selected.append(cal)
    return selected


async def sync_all(db: Session) -> dict[str, Any]:
    """Sync every selected calendar. Returns a per-calendar summary."""
    token = await get_valid_access_token(db)
    if not token:
        raise RuntimeError("Google no está conectado")

    calendars = await gs.list_calendars(token)
    selected = _selectable_calendars(calendars)
    live_ids = {cal["id"] for cal in selected}

    results = []
    for cal in selected:
        calendar_id = cal["id"]
        try:
            result = await sync_calendar(db, token, calendar_id)
            result["summary"] = cal.get("summary")
            results.append(result)
        except httpx.HTTPStatusError as exc:
            logger.error("[google] Sync failed for %s: HTTP %s", calendar_id, exc.response.status_code)
            state = (
                db.query(GoogleCalendarSyncState)
                .filter(GoogleCalendarSyncState.user_id == 1, GoogleCalendarSyncState.calendar_id == calendar_id)
                .first()
            )
            if state:
                state.last_error = f"HTTP {exc.response.status_code}"
                db.commit()
            results.append({"calendar_id": calendar_id, "error": f"HTTP {exc.response.status_code}"})
        except Exception as exc:  # keep syncing the remaining calendars
            logger.error("[google] Sync failed for %s: %s", calendar_id, exc)
            # Generic message — str(exc) can embed URLs/paths that must not
            # be reflected back through the API response (#1332).
            results.append({"calendar_id": calendar_id, "error": "Sync failed"})

    # Prune state (and cached events) for calendars removed from the account.
    stale = db.query(GoogleCalendarSyncState).filter(GoogleCalendarSyncState.user_id == 1).all()
    for row in stale:
        if row.calendar_id not in live_ids:
            db.query(GoogleCalendarEvent).filter(
                GoogleCalendarEvent.user_id == 1,
                GoogleCalendarEvent.calendar_id == row.calendar_id,
            ).delete()
            db.delete(row)
    db.commit()

    return {"synced_at": datetime.now(UTC).isoformat(), "calendars": results}


def get_cached_events(
    db: Session,
    start: datetime | None = None,
    end: datetime | None = None,
    calendar_id: str | None = None,
) -> list[GoogleCalendarEvent]:
    """Read events from the local cache, ordered by start."""
    query = db.query(GoogleCalendarEvent).filter(
        GoogleCalendarEvent.user_id == 1,
        GoogleCalendarEvent.status != "cancelled",
    )
    if calendar_id:
        query = query.filter(GoogleCalendarEvent.calendar_id == calendar_id)
    if start is not None:
        query = query.filter(GoogleCalendarEvent.start_at >= start)
    if end is not None:
        query = query.filter(GoogleCalendarEvent.start_at <= end)
    events: list[GoogleCalendarEvent] = query.order_by(GoogleCalendarEvent.start_at).all()
    return events


def get_sync_status(db: Session) -> dict[str, Any]:
    """Aggregate sync state: last sync time, calendar count, cached events."""
    states = db.query(GoogleCalendarSyncState).filter(GoogleCalendarSyncState.user_id == 1).all()
    last_synced = max((s.last_synced_at for s in states if s.last_synced_at), default=None)
    events = db.query(GoogleCalendarEvent).filter(GoogleCalendarEvent.user_id == 1).count()
    return {
        "calendars": len(states),
        "last_synced_at": last_synced.isoformat() if last_synced else None,
        "cached_events": events,
    }


# ── Write-back (#1233) ─────────────────────────────────────────────────────────
#
# Creating, editing, or deleting Google Calendar events from joidy. Every write
# is mirrored into the local cache immediately (via _upsert_event) so the UI
# reflects the change without waiting for the next incremental sync.
#
# The OAuth flow now requests the `calendar.events` scope. Tokens granted
# before that change only have `calendar.readonly`, so Google answers 403
# INSUFFICIENT_PERMISSIONS — surfaced as GoogleReconsentRequired so the UI can
# guide the user to reconnect.


class GoogleReconsentRequired(RuntimeError):
    """The stored token lacks the calendar.events scope (re-connect needed)."""


def _reconsent_if_needed(exc: httpx.HTTPStatusError) -> None:
    """Raise GoogleReconsentRequired when the token lacks write scope."""
    response = exc.response
    if response.status_code == 403:
        try:
            body = response.json()
        except Exception:
            body = {}
        errors = body.get("error", {})
        if isinstance(errors, dict) and errors.get("errors"):
            reasons = {e.get("reason") for e in errors["errors"]}
            if "insufficientPermissions" in reasons:
                raise GoogleReconsentRequired(
                    "El token de Google no tiene permiso de escritura. Reconecta tu cuenta en Ajustes."
                ) from exc
    raise exc


async def create_google_event(
    db: Session,
    token: str,
    calendar_id: str,
    summary: str,
    start: dict[str, Any],
    end: dict[str, Any],
    description: str | None = None,
) -> dict[str, Any]:
    """Create an event in Google and upsert it into the local cache."""
    event: dict[str, Any] = {"summary": summary, "start": start, "end": end}
    if description:
        event["description"] = description
    try:
        created = await gs.create_event(token, calendar_id, event)
    except httpx.HTTPStatusError as exc:
        _reconsent_if_needed(exc)
    _upsert_event(db, calendar_id, created)
    db.commit()
    return created


async def update_google_event(
    db: Session,
    token: str,
    calendar_id: str,
    google_event_id: str,
    patch: dict[str, Any],
) -> dict[str, Any]:
    """Patch an event in Google and upsert the result into the local cache."""
    try:
        updated = await gs.patch_event(token, calendar_id, google_event_id, patch)
    except httpx.HTTPStatusError as exc:
        _reconsent_if_needed(exc)
    _upsert_event(db, calendar_id, updated)
    db.commit()
    return updated


async def delete_google_event(
    db: Session,
    token: str,
    calendar_id: str,
    google_event_id: str,
) -> None:
    """Delete an event in Google and drop it from the local cache."""
    try:
        await gs.delete_event(token, calendar_id, google_event_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            # Already gone remotely — just drop the local cache row.
            pass
        else:
            _reconsent_if_needed(exc)
    db.query(GoogleCalendarEvent).filter(
        GoogleCalendarEvent.user_id == 1,
        GoogleCalendarEvent.calendar_id == calendar_id,
        GoogleCalendarEvent.google_id == google_event_id,
    ).delete()
    db.commit()
