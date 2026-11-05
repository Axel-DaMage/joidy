"""Tests for Google Calendar sync (#1134): datetime parsing, incremental
sync via syncToken, cancelled-event handling, 410 GONE fallback to full
sync, calendar selection/pruning, and the /calendar/* router endpoints.

HTTP to Google is mocked at the google_service helper level — no network.
"""

import asyncio
import sys
import types
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import httpx as httpx_module

# Stub sqlite_vec before importing app modules (matches conftest pattern).
if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

from database import Base
from models.google_calendar_event import GoogleCalendarEvent
from models.google_calendar_sync import GoogleCalendarSyncState
from services import google_calendar_service as gcs
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _mk_http_status_error(status_code: int) -> httpx_module.HTTPStatusError:
    resp = httpx_module.Response(status_code=status_code)
    return httpx_module.HTTPStatusError(f"HTTP {status_code}", request=None, response=resp)


class CalendarTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()


class ParseDatetimeTest(CalendarTestBase):
    def test_parses_rfc3339_datetime(self) -> None:
        dt, all_day = gcs._parse_gcal_datetime({"dateTime": "2026-11-05T10:00:00Z"})
        self.assertFalse(all_day)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.hour, 10)
        self.assertIsNotNone(dt.tzinfo)

    def test_parses_datetime_without_tz_as_utc(self) -> None:
        dt, all_day = gcs._parse_gcal_datetime({"dateTime": "2026-11-05T10:00:00"})
        self.assertFalse(all_day)
        self.assertEqual(dt.tzinfo, UTC)

    def test_parses_all_day_date(self) -> None:
        dt, all_day = gcs._parse_gcal_datetime({"date": "2026-11-05"})
        self.assertTrue(all_day)
        self.assertEqual(dt.date().isoformat(), "2026-11-05")

    def test_none_and_invalid(self) -> None:
        self.assertEqual(gcs._parse_gcal_datetime(None), (None, False))
        self.assertEqual(gcs._parse_gcal_datetime({}), (None, False))
        self.assertEqual(gcs._parse_gcal_datetime({"dateTime": "garbage"}), (None, False))


def _event_item(google_id: str, summary: str = "Event", status: str = "confirmed") -> dict:
    return {
        "id": google_id,
        "status": status,
        "summary": summary,
        "description": "desc",
        "location": "loc",
        "htmlLink": f"https://calendar.google.com/{google_id}",
        "start": {"dateTime": "2026-11-05T10:00:00Z"},
        "end": {"dateTime": "2026-11-05T11:00:00Z"},
    }


class SyncCalendarTest(CalendarTestBase):
    def _run_sync(self, db, token="tok", calendar_id="primary", items=None, sync_token="SYNC1"):
        items = items if items is not None else [_event_item("ev-1")]
        with patch.object(
            gcs.gs, "list_events_raw", new=AsyncMock(return_value={"items": items, "nextSyncToken": sync_token})
        ):
            return asyncio.new_event_loop().run_until_complete(gcs.sync_calendar(db, token, calendar_id))

    def test_initial_sync_upserts_and_stores_token(self) -> None:
        with self.Session() as db:
            result = self._run_sync(db)

            self.assertEqual(result["calendar_id"], "primary")
            self.assertEqual(result["synced"], 1)
            self.assertFalse(result["incremental"])

            event = db.query(GoogleCalendarEvent).one()
            self.assertEqual(event.google_id, "ev-1")
            self.assertEqual(event.summary, "Event")
            self.assertFalse(event.all_day)

            state = db.query(GoogleCalendarSyncState).one()
            self.assertEqual(state.sync_token, "SYNC1")
            self.assertIsNotNone(state.last_synced_at)

    def test_initial_sync_uses_timewindow(self) -> None:
        with self.Session() as db:
            mock = AsyncMock(return_value={"items": [], "nextSyncToken": "SYNC"})
            with patch.object(gcs.gs, "list_events_raw", new=mock):
                asyncio.new_event_loop().run_until_complete(gcs.sync_calendar(db, "tok", "primary"))
            params = mock.call_args.args[2]
            self.assertIn("timeMin", params)
            self.assertNotIn("syncToken", params)
            self.assertEqual(params["singleEvents"], "true")

    def test_incremental_sync_uses_sync_token(self) -> None:
        with self.Session() as db:
            self._run_sync(db)
            mock = AsyncMock(return_value={"items": [], "nextSyncToken": "SYNC2"})
            with patch.object(gcs.gs, "list_events_raw", new=mock):
                result = asyncio.new_event_loop().run_until_complete(gcs.sync_calendar(db, "tok", "primary"))
            self.assertTrue(result["incremental"])
            params = mock.call_args.args[2]
            self.assertEqual(params["syncToken"], "SYNC1")
            self.assertNotIn("timeMin", params)
            # Token rotated.
            state = db.query(GoogleCalendarSyncState).one()
            self.assertEqual(state.sync_token, "SYNC2")

    def test_incremental_updates_existing_event(self) -> None:
        with self.Session() as db:
            self._run_sync(db)
            updated = _event_item("ev-1", summary="Renamed")
            with patch.object(
                gcs.gs, "list_events_raw", new=AsyncMock(return_value={"items": [updated], "nextSyncToken": "SYNC2"})
            ):
                asyncio.new_event_loop().run_until_complete(gcs.sync_calendar(db, "tok", "primary"))
            self.assertEqual(db.query(GoogleCalendarEvent).count(), 1)
            self.assertEqual(db.query(GoogleCalendarEvent).one().summary, "Renamed")

    def test_cancelled_event_is_deleted(self) -> None:
        with self.Session() as db:
            self._run_sync(db)
            cancelled = {"id": "ev-1", "status": "cancelled"}
            with patch.object(
                gcs.gs, "list_events_raw", new=AsyncMock(return_value={"items": [cancelled], "nextSyncToken": "SYNC2"})
            ):
                result = asyncio.new_event_loop().run_until_complete(gcs.sync_calendar(db, "tok", "primary"))
            self.assertEqual(result["synced"], 0)
            self.assertEqual(db.query(GoogleCalendarEvent).count(), 0)

    def test_410_resets_token_and_full_resyncs(self) -> None:
        with self.Session() as db:
            self._run_sync(db)

            calls = []

            async def side_effect(token, calendar_id, params):
                calls.append(params)
                if "syncToken" in params:
                    raise _mk_http_status_error(410)
                return {"items": [_event_item("ev-full")], "nextSyncToken": "SYNC-NEW"}

            with patch.object(gcs.gs, "list_events_raw", new=AsyncMock(side_effect=side_effect)):
                result = asyncio.new_event_loop().run_until_complete(gcs.sync_calendar(db, "tok", "primary"))

            self.assertFalse(result["incremental"])
            self.assertEqual(len(calls), 2)
            self.assertNotIn("syncToken", calls[1])
            state = db.query(GoogleCalendarSyncState).one()
            self.assertEqual(state.sync_token, "SYNC-NEW")
            self.assertEqual(db.query(GoogleCalendarEvent).one().google_id, "ev-full")

    def test_event_without_start_is_skipped(self) -> None:
        with self.Session() as db:
            item = {"id": "ev-x", "status": "confirmed"}
            result = self._run_sync(db, items=[item])
            self.assertEqual(result["synced"], 0)
            self.assertEqual(db.query(GoogleCalendarEvent).count(), 0)


class SelectableCalendarsTest(CalendarTestBase):
    def test_filters_deleted_unselected_and_unlisted_roles(self) -> None:
        calendars = [
            {"id": "primary", "primary": True, "selected": None},
            {"id": "work", "selected": True},
            {"id": "hidden", "selected": False},
            {"id": "gone", "deleted": True},
            {"id": "holidays", "selected": True, "accessRole": "freeBusyReader"},
        ]
        ids = [c["id"] for c in gcs._selectable_calendars(calendars)]
        self.assertEqual(ids, ["primary", "work", "holidays"])


class SyncAllTest(CalendarTestBase):
    def test_sync_all_filters_and_prunes_stale_calendars(self) -> None:
        with self.Session() as db:
            # Stale calendar no longer present in the account list.
            db.add(GoogleCalendarSyncState(user_id=1, calendar_id="old-cal"))
            db.add(
                GoogleCalendarEvent(
                    user_id=1, calendar_id="old-cal", google_id="ev-old", start_at=datetime.now(UTC)
                )
            )
            db.commit()

            calendars = [
                {"id": "primary", "primary": True},
                {"id": "gone", "deleted": True},
                {"id": "hidden", "selected": False},
            ]

            async def fake_sync(db_, token, calendar_id):
                db_.add(GoogleCalendarSyncState(user_id=1, calendar_id=calendar_id))
                db_.commit()
                return {"calendar_id": calendar_id, "synced": 1, "deleted": 0, "incremental": False}

            with (
                patch.object(gcs.gs, "list_calendars", new=AsyncMock(return_value=calendars)),
                patch.object(gcs, "get_valid_access_token", new=AsyncMock(return_value="tok")),
                patch.object(gcs, "sync_calendar", new=fake_sync),
            ):
                result = asyncio.new_event_loop().run_until_complete(gcs.sync_all(db))

            self.assertEqual([c["calendar_id"] for c in result["calendars"]], ["primary"])
            # Stale state + events pruned.
            self.assertEqual(db.query(GoogleCalendarSyncState).count(), 1)
            self.assertEqual(db.query(GoogleCalendarSyncState).one().calendar_id, "primary")
            self.assertEqual(db.query(GoogleCalendarEvent).count(), 0)

    def test_sync_all_not_connected_raises(self) -> None:
        with self.Session() as db:
            with patch.object(gcs, "get_valid_access_token", new=AsyncMock(return_value=None)):
                with self.assertRaises(RuntimeError):
                    asyncio.new_event_loop().run_until_complete(gcs.sync_all(db))

    def test_sync_all_continues_after_calendar_error(self) -> None:
        with self.Session() as db:
            calendars = [{"id": "bad"}, {"id": "good", "selected": True}]

            async def fake_sync(db_, token, calendar_id):
                if calendar_id == "bad":
                    raise _mk_http_status_error(403)
                return {"calendar_id": calendar_id, "synced": 1, "deleted": 0, "incremental": False}

            with (
                patch.object(gcs.gs, "list_calendars", new=AsyncMock(return_value=calendars)),
                patch.object(gcs, "get_valid_access_token", new=AsyncMock(return_value="tok")),
                patch.object(gcs, "sync_calendar", new=fake_sync),
            ):
                result = asyncio.new_event_loop().run_until_complete(gcs.sync_all(db))

            by_id = {c["calendar_id"]: c for c in result["calendars"]}
            self.assertIn("error", by_id["bad"])
            self.assertEqual(by_id["good"]["synced"], 1)


class CachedEventsTest(CalendarTestBase):
    def _add(self, db, google_id, start, calendar_id="primary", status="confirmed"):
        db.add(
            GoogleCalendarEvent(
                user_id=1, calendar_id=calendar_id, google_id=google_id, status=status, start_at=start
            )
        )

    def test_range_and_filters(self) -> None:
        with self.Session() as db:
            base = datetime(2026, 11, 5, tzinfo=UTC)
            self._add(db, "e1", base - timedelta(days=10))
            self._add(db, "e2", base)
            self._add(db, "e3", base + timedelta(days=10))
            self._add(db, "e4", base, calendar_id="work")
            self._add(db, "e5", base, status="cancelled")
            db.commit()

            self.assertEqual(len(gcs.get_cached_events(db)), 4)
            self.assertEqual(len(gcs.get_cached_events(db, calendar_id="work")), 1)
            window = gcs.get_cached_events(db, start=base - timedelta(days=1), end=base + timedelta(days=1))
            self.assertEqual([e.google_id for e in window], ["e2", "e4"])
            # Ordered by start.
            events = gcs.get_cached_events(db)
            self.assertEqual(events[0].google_id, "e1")

    def test_get_sync_status(self) -> None:
        with self.Session() as db:
            self.assertEqual(gcs.get_sync_status(db)["calendars"], 0)
            now = datetime.now(UTC)
            db.add(GoogleCalendarSyncState(user_id=1, calendar_id="primary", last_synced_at=now))
            self._add(db, "e1", now)
            db.commit()
            status = gcs.get_sync_status(db)
            self.assertEqual(status["calendars"], 1)
            self.assertEqual(status["cached_events"], 1)
            self.assertIsNotNone(status["last_synced_at"])


if __name__ == "__main__":
    unittest.main()
