"""Tests for Google Calendar write-back (#1233): create/patch/delete event
helpers, local-cache mirroring, and 403 insufficientPermissions →
GoogleReconsentRequired mapping.

HTTP to Google is mocked at the google_service helper level — no network.
"""

import sys
import types
import unittest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import httpx as httpx_module

# Stub sqlite_vec before importing app modules (matches conftest pattern).
if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

from database import Base
from models.google_calendar_event import GoogleCalendarEvent
from services import google_calendar_service as gcs
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _mk_http_status_error(status_code: int, body: dict | None = None) -> httpx_module.HTTPStatusError:
    request = httpx_module.Request("POST", "https://googleapis.example/calendar/v3")
    resp = httpx_module.Response(status_code=status_code, request=request, json=body or {})
    return httpx_module.HTTPStatusError(f"HTTP {status_code}", request=request, response=resp)


def _forbidden() -> httpx_module.HTTPStatusError:
    return _mk_http_status_error(
        403,
        {
            "error": {
                "errors": [
                    {
                        "domain": "calendar",
                        "reason": "insufficientPermissions",
                        "message": "Insufficient Permission",
                    }
                ]
            }
        },
    )


class WriteBackTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()


class CreateEventTest(WriteBackTestBase):
    def test_create_upserts_local_cache(self) -> None:
        created = {
            "id": "evt-1",
            "summary": "Joidy task",
            "status": "confirmed",
            "start": {"dateTime": "2026-11-20T10:00:00Z"},
            "end": {"dateTime": "2026-11-20T11:00:00Z"},
        }
        with patch.object(gcs.gs, "create_event", new=AsyncMock(return_value=created)):
            result = asyncio_run(
                gcs.create_google_event(
                    self.db,
                    "tok",
                    "primary",
                    "Joidy task",
                    {"dateTime": "2026-11-20T10:00:00Z"},
                    {"dateTime": "2026-11-20T11:00:00Z"},
                )
            )
        self.assertEqual(result["id"], "evt-1")
        row = self.db.query(GoogleCalendarEvent).filter_by(google_id="evt-1").one()
        self.assertEqual(row.summary, "Joidy task")
        self.assertEqual(row.calendar_id, "primary")

    def test_create_403_maps_to_reconsent(self) -> None:
        with patch.object(gcs.gs, "create_event", new=AsyncMock(side_effect=_forbidden())):
            with self.assertRaises(gcs.GoogleReconsentRequired):
                asyncio_run(
                    gcs.create_google_event(
                        self.db,
                        "tok",
                        "primary",
                        "x",
                        {"dateTime": "2026-11-20T10:00:00Z"},
                        {"dateTime": "2026-11-20T11:00:00Z"},
                    )
                )


class UpdateEventTest(WriteBackTestBase):
    def test_patch_upserts_local_cache(self) -> None:
        updated = {
            "id": "evt-1",
            "summary": "Renamed",
            "status": "confirmed",
            "start": {"dateTime": "2026-11-20T10:00:00Z"},
            "end": {"dateTime": "2026-11-20T12:00:00Z"},
        }
        with patch.object(gcs.gs, "patch_event", new=AsyncMock(return_value=updated)):
            result = asyncio_run(
                gcs.update_google_event(self.db, "tok", "primary", "evt-1", {"summary": "Renamed"})
            )
        self.assertEqual(result["summary"], "Renamed")
        row = self.db.query(GoogleCalendarEvent).filter_by(google_id="evt-1").one()
        self.assertEqual(row.summary, "Renamed")

    def test_patch_403_maps_to_reconsent(self) -> None:
        with patch.object(gcs.gs, "patch_event", new=AsyncMock(side_effect=_forbidden())):
            with self.assertRaises(gcs.GoogleReconsentRequired):
                asyncio_run(gcs.update_google_event(self.db, "tok", "primary", "evt-1", {}))


class DeleteEventTest(WriteBackTestBase):
    def test_delete_drops_local_cache(self) -> None:
        self.db.add(
            GoogleCalendarEvent(
                user_id=1,
                calendar_id="primary",
                google_id="evt-1",
                summary="x",
                start_at=datetime(2026, 11, 20, 10, 0, tzinfo=UTC),
            )
        )
        self.db.commit()
        with patch.object(gcs.gs, "delete_event", new=AsyncMock(return_value=None)):
            asyncio_run(gcs.delete_google_event(self.db, "tok", "primary", "evt-1"))
        self.assertEqual(self.db.query(GoogleCalendarEvent).filter_by(google_id="evt-1").count(), 0)

    def test_delete_404_remote_still_drops_local(self) -> None:
        self.db.add(
            GoogleCalendarEvent(
                user_id=1,
                calendar_id="primary",
                google_id="evt-gone",
                summary="x",
                start_at=datetime(2026, 11, 20, 10, 0, tzinfo=UTC),
            )
        )
        self.db.commit()
        with patch.object(gcs.gs, "delete_event", new=AsyncMock(side_effect=_mk_http_status_error(404))):
            asyncio_run(gcs.delete_google_event(self.db, "tok", "primary", "evt-gone"))
        self.assertEqual(self.db.query(GoogleCalendarEvent).filter_by(google_id="evt-gone").count(), 0)

    def test_delete_403_maps_to_reconsent(self) -> None:
        with patch.object(gcs.gs, "delete_event", new=AsyncMock(side_effect=_forbidden())):
            with self.assertRaises(gcs.GoogleReconsentRequired):
                asyncio_run(gcs.delete_google_event(self.db, "tok", "primary", "evt-1"))


class ReconsentDetectionTest(WriteBackTestBase):
    def test_other_403_reraises_original(self) -> None:
        exc = _mk_http_status_error(403, {"error": {"errors": [{"reason": "rateLimitExceeded"}]}})
        with self.assertRaises(httpx_module.HTTPStatusError):
            gcs._reconsent_if_needed(exc)

    def test_401_reraises_original(self) -> None:
        exc = _mk_http_status_error(401)
        with self.assertRaises(httpx_module.HTTPStatusError):
            gcs._reconsent_if_needed(exc)


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)
