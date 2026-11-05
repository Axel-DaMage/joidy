"""Endpoint tests for the Google Calendar sync router (#1134).

Uses the shared ``client`` fixture (auth mocked to user 1). Google HTTP
traffic is mocked at the service boundary.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from models.google_calendar_event import GoogleCalendarEvent


def test_calendar_status_empty(client):
    resp = client.get("/integrations/google/calendar/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["connected"] is False
    assert body["calendars"] == 0
    assert body["cached_events"] == 0
    assert body["last_synced_at"] is None


def test_calendar_sync_not_connected_returns_401(client):
    with patch(
        "services.google_calendar_service.get_valid_access_token", new=AsyncMock(return_value=None)
    ):
        resp = client.post("/integrations/google/calendar/sync")
    assert resp.status_code == 401


def test_calendar_sync_returns_summary(client):
    summary = {
        "synced_at": datetime.now(UTC).isoformat(),
        "calendars": [{"calendar_id": "primary", "synced": 3, "deleted": 1, "incremental": False}],
    }
    with (
            patch("services.google_calendar_service.get_valid_access_token", new=AsyncMock(return_value="tok")),
            patch(
                "services.google_calendar_service.gs.list_calendars",
                new=AsyncMock(return_value=[{"id": "primary", "primary": True}]),
            ),
        patch("services.google_calendar_service.sync_calendar", new=AsyncMock(return_value=summary["calendars"][0])),
    ):
        resp = client.post("/integrations/google/calendar/sync")
    assert resp.status_code == 200
    body = resp.json()
    assert body["synced_at"]
    assert body["calendars"][0]["calendar_id"] == "primary"
    assert body["calendars"][0]["synced"] == 3


def test_calendar_events_returns_cached(client, db_session):
    now = datetime.now(UTC)
    db_session.add(
        GoogleCalendarEvent(
            user_id=1,
            calendar_id="primary",
            google_id="ev-1",
            summary="Reunión",
            all_day=False,
            status="confirmed",
            start_at=now + timedelta(days=1),
            end_at=now + timedelta(days=1, hours=1),
        )
    )
    db_session.commit()

    resp = client.get("/integrations/google/calendar/events")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 1
    assert events[0]["google_id"] == "ev-1"
    assert events[0]["summary"] == "Reunión"
    assert events[0]["calendar_id"] == "primary"
    assert events[0]["all_day"] is False


def test_calendar_events_filters_by_range(client, db_session):
    now = datetime.now(UTC)
    for gid, days in (("past", -5), ("soon", 1), ("far", 60)):
        db_session.add(
            GoogleCalendarEvent(
                user_id=1,
                calendar_id="primary",
                google_id=gid,
                status="confirmed",
                start_at=now + timedelta(days=days),
            )
        )
    db_session.commit()

    start = now + timedelta(days=-1)
    end = now + timedelta(days=7)
    resp = client.get(
        "/integrations/google/calendar/events",
        params={"start": start.isoformat(), "end": end.isoformat()},
    )
    assert resp.status_code == 200
    assert [e["google_id"] for e in resp.json()] == ["soon"]


def test_calendar_events_requires_auth(client_no_auth):
    resp = client_no_auth.get("/integrations/google/calendar/events")
    assert resp.status_code in (401, 403)
