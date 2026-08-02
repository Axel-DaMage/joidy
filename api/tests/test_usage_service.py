"""Unit tests for usage_service — track_event, get_usage_summary, get_feature_usage.

Uses in-memory SQLite and stubs sqlite_vec (matches conftest pattern).
"""

import sys
import types
import unittest
from datetime import UTC, datetime, timedelta

# Stub sqlite_vec before importing app modules (matches conftest pattern).
if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

from database import Base
from models.usage_event import UsageEvent
from services.usage_service import (
    EVENT_FEATURE_USE,
    EVENT_PAGE_VIEW,
    EVENT_SESSION_END,
    EVENT_SESSION_START,
    get_feature_usage,
    get_usage_summary,
    track_event,
)
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class UsageServiceTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        # tag_cooccurrences is referenced by some models but not always
        # created cleanly on SQLite; ensure it exists to avoid spurious errors.
        with self.engine.begin() as conn:
            try:
                conn.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS tag_cooccurrences "
                        "(tag_a_id INTEGER, tag_b_id INTEGER, weight INTEGER, "
                        "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
                    )
                )
            except Exception:
                pass
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()

    def _now(self) -> datetime:
        return datetime.now(UTC)


class TrackEventTest(UsageServiceTestBase):
    def test_track_page_view(self):
        db = self.Session()
        event = track_event(db, user_id=1, event_type=EVENT_PAGE_VIEW, event_data={"path": "/notes"})
        self.assertEqual(event.event_type, EVENT_PAGE_VIEW)
        self.assertEqual(event.user_id, 1)
        self.assertEqual(event.event_data, {"path": "/notes"})
        self.assertIsNotNone(event.created_at)
        db.close()

    def test_track_feature_use(self):
        db = self.Session()
        event = track_event(db, user_id=2, event_type=EVENT_FEATURE_USE, event_data={"feature": "search"})
        self.assertEqual(event.event_type, EVENT_FEATURE_USE)
        self.assertEqual(event.event_data, {"feature": "search"})
        db.close()

    def test_track_session_start_end(self):
        db = self.Session()
        s = track_event(db, user_id=1, event_type=EVENT_SESSION_START)
        e = track_event(db, user_id=1, event_type=EVENT_SESSION_END)
        self.assertEqual(s.event_type, EVENT_SESSION_START)
        self.assertEqual(e.event_type, EVENT_SESSION_END)
        db.close()

    def test_track_event_no_data(self):
        db = self.Session()
        event = track_event(db, user_id=1, event_type=EVENT_SESSION_START)
        self.assertIsNone(event.event_data)
        db.close()

    def test_invalid_event_type_raises(self):
        db = self.Session()
        with self.assertRaises(ValueError):
            track_event(db, user_id=1, event_type="bogus", event_data={})
        db.close()

    def test_events_are_separate_per_user(self):
        db = self.Session()
        track_event(db, user_id=1, event_type=EVENT_PAGE_VIEW, event_data={"path": "/a"})
        track_event(db, user_id=2, event_type=EVENT_PAGE_VIEW, event_data={"path": "/b"})
        count1 = db.query(UsageEvent).filter(UsageEvent.user_id == 1).count()
        count2 = db.query(UsageEvent).filter(UsageEvent.user_id == 2).count()
        self.assertEqual(count1, 1)
        self.assertEqual(count2, 1)
        db.close()


class GetUsageSummaryTest(UsageServiceTestBase):
    def test_empty_summary(self):
        db = self.Session()
        summary = get_usage_summary(db, user_id=1, days=30)
        self.assertEqual(summary["total_events"], 0)
        self.assertEqual(summary["session_count"], 0)
        self.assertEqual(summary["active_days"], 0)
        self.assertEqual(summary["avg_session_duration_min"], 0.0)
        self.assertEqual(summary["top_features"], [])
        self.assertEqual(summary["top_pages"], [])
        db.close()

    def test_total_events_and_session_count(self):
        db = self.Session()
        track_event(db, 1, EVENT_SESSION_START)
        track_event(db, 1, EVENT_PAGE_VIEW, {"path": "/notes"})
        track_event(db, 1, EVENT_FEATURE_USE, {"feature": "search"})
        track_event(db, 1, EVENT_SESSION_END)
        summary = get_usage_summary(db, user_id=1, days=30)
        self.assertEqual(summary["total_events"], 4)
        self.assertEqual(summary["session_count"], 1)
        db.close()

    def test_active_days_counts_distinct_days(self):
        db = self.Session()
        now = self._now()
        # Two events on different days.
        db.add(UsageEvent(user_id=1, event_type=EVENT_PAGE_VIEW, event_data={"path": "/a"}, created_at=now))
        db.add(
            UsageEvent(
                user_id=1,
                event_type=EVENT_PAGE_VIEW,
                event_data={"path": "/b"},
                created_at=now - timedelta(days=2),
            )
        )
        db.commit()
        summary = get_usage_summary(db, user_id=1, days=30)
        self.assertEqual(summary["active_days"], 2)
        db.close()

    def test_excludes_events_outside_window(self):
        db = self.Session()
        old = self._now() - timedelta(days=40)
        db.add(UsageEvent(user_id=1, event_type=EVENT_PAGE_VIEW, event_data={"path": "/old"}, created_at=old))
        db.commit()
        summary = get_usage_summary(db, user_id=1, days=30)
        self.assertEqual(summary["total_events"], 0)
        db.close()

    def test_avg_session_duration(self):
        db = self.Session()
        now = self._now()
        start = now - timedelta(minutes=10)
        db.add(UsageEvent(user_id=1, event_type=EVENT_SESSION_START, created_at=start))
        db.add(UsageEvent(user_id=1, event_type=EVENT_SESSION_END, created_at=now))
        db.commit()
        summary = get_usage_summary(db, user_id=1, days=30)
        # ~10 minutes; allow some tolerance for test timing.
        self.assertGreater(summary["avg_session_duration_min"], 9.0)
        self.assertLess(summary["avg_session_duration_min"], 11.5)
        db.close()

    def test_top_features_and_pages(self):
        db = self.Session()
        track_event(db, 1, EVENT_FEATURE_USE, {"feature": "search"})
        track_event(db, 1, EVENT_FEATURE_USE, {"feature": "search"})
        track_event(db, 1, EVENT_FEATURE_USE, {"feature": "tag"})
        track_event(db, 1, EVENT_PAGE_VIEW, {"path": "/notes"})
        track_event(db, 1, EVENT_PAGE_VIEW, {"path": "/goals"})
        track_event(db, 1, EVENT_PAGE_VIEW, {"path": "/goals"})
        summary = get_usage_summary(db, user_id=1, days=30)
        self.assertEqual(summary["top_features"][0], {"feature": "search", "count": 2})
        self.assertEqual(summary["top_features"][1], {"feature": "tag", "count": 1})
        self.assertEqual(summary["top_pages"][0], {"path": "/goals", "count": 2})
        self.assertEqual(summary["top_pages"][1], {"path": "/notes", "count": 1})
        db.close()

    def test_days_clamped(self):
        db = self.Session()
        # days < 1 clamped to 1, days > 366 clamped to 366 — no crash.
        s0 = get_usage_summary(db, user_id=1, days=0)
        self.assertEqual(s0["days"], 1)
        s1 = get_usage_summary(db, user_id=1, days=999)
        self.assertEqual(s1["days"], 366)
        db.close()

    def test_isolated_per_user(self):
        db = self.Session()
        track_event(db, 1, EVENT_PAGE_VIEW, {"path": "/a"})
        track_event(db, 2, EVENT_PAGE_VIEW, {"path": "/b"})
        track_event(db, 2, EVENT_PAGE_VIEW, {"path": "/b"})
        s1 = get_usage_summary(db, user_id=1, days=30)
        s2 = get_usage_summary(db, user_id=2, days=30)
        self.assertEqual(s1["total_events"], 1)
        self.assertEqual(s2["total_events"], 2)
        db.close()


class GetFeatureUsageTest(UsageServiceTestBase):
    def test_empty(self):
        db = self.Session()
        self.assertEqual(get_feature_usage(db, user_id=1, days=30), [])
        db.close()

    def test_ranked_by_count(self):
        db = self.Session()
        track_event(db, 1, EVENT_FEATURE_USE, {"feature": "a"})
        track_event(db, 1, EVENT_FEATURE_USE, {"feature": "b"})
        track_event(db, 1, EVENT_FEATURE_USE, {"feature": "b"})
        track_event(db, 1, EVENT_FEATURE_USE, {"feature": "b"})
        result = get_feature_usage(db, user_id=1, days=30)
        self.assertEqual(result[0], {"feature": "b", "count": 3})
        self.assertEqual(result[1], {"feature": "a", "count": 1})
        db.close()

    def test_ignores_other_event_types(self):
        db = self.Session()
        track_event(db, 1, EVENT_PAGE_VIEW, {"path": "/notes"})
        track_event(db, 1, EVENT_FEATURE_USE, {"feature": "search"})
        result = get_feature_usage(db, user_id=1, days=30)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], {"feature": "search", "count": 1})
        db.close()

    def test_excludes_outside_window(self):
        db = self.Session()
        old = self._now() - timedelta(days=40)
        db.add(UsageEvent(user_id=1, event_type=EVENT_FEATURE_USE, event_data={"feature": "old"}, created_at=old))
        db.commit()
        self.assertEqual(get_feature_usage(db, user_id=1, days=30), [])
        db.close()


if __name__ == "__main__":
    unittest.main()
