"""Tests for XP award idempotency (#1320, B-04).

Anti-farming contract: XP events that carry a ``dedup_key`` can only ever
award once — at the router level (replayed /complete, re-parent toggling)
and at the engine level (the (event_type, dedup_key) partial unique index
on xp_events is the hard backstop for the pre-check).
"""

import sys
import types
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

import services.gamification_engine as ge
from database import Base
from models.gamification import UserStats, XPEvent
from repositories import XPEventRepository


class EngineDedupTest(unittest.TestCase):
    """Engine-level idempotency on an isolated in-memory SQLite DB."""

    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        ge._xp_table_cache = None
        ge._plant_stages_cache = None

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def _seed_daily_activity(self) -> None:
        """Pre-seed today's activity so the daily_activity bonus is not
        double-counted on top of the event XP."""
        stats = ge._get_or_create_stats(self.db)
        stats.last_activity_date = ge._today_utc()
        self.db.commit()

    def test_dedup_key_awards_once(self) -> None:
        self._seed_daily_activity()
        key = f"pomodoro:{uuid4().hex}"

        first = ge.process_event(self.db, "pomodoro_completed", {"pomodoro_id": key}, dedup_key=key)
        second = ge.process_event(self.db, "pomodoro_completed", {"pomodoro_id": key}, dedup_key=key)

        self.assertEqual(first.xp_awarded, 15)
        self.assertEqual(second.xp_awarded, 0)
        events = self.db.query(XPEvent).filter(XPEvent.event_type == "pomodoro_completed").all()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].dedup_key, key)

    def test_distinct_dedup_keys_all_award(self) -> None:
        self._seed_daily_activity()
        for _ in range(3):
            result = ge.process_event(self.db, "pomodoro_completed", dedup_key=f"pomodoro:{uuid4().hex}")
            self.assertEqual(result.xp_awarded, 15)
        events = self.db.query(XPEvent).filter(XPEvent.event_type == "pomodoro_completed").all()
        self.assertEqual(len(events), 3)

    def test_no_dedup_key_keeps_legacy_behavior(self) -> None:
        self._seed_daily_activity()
        for _ in range(2):
            result = ge.process_event(self.db, "note_created", {"note_id": 1})
            self.assertEqual(result.xp_awarded, 10)

    def test_unique_index_is_the_backstop(self) -> None:
        """A pre-seeded event row makes a racing process_event a no-op, and a
        direct duplicate insert raises IntegrityError."""
        self._seed_daily_activity()
        key = f"goal:{uuid4().hex}"
        self.db.add(XPEvent(event_type="goal_completed", xp=50, dedup_key=key))
        self.db.commit()

        result = ge.process_event(self.db, "goal_completed", {"goal_id": 1}, dedup_key=key)
        self.assertEqual(result.xp_awarded, 0)
        stats = self.db.query(UserStats).first()
        assert stats is not None
        self.assertEqual(stats.total_xp, 0)

        self.db.add(XPEvent(event_type="goal_completed", xp=50, dedup_key=key))
        with self.assertRaises(IntegrityError):
            self.db.flush()
        self.db.rollback()

    def test_repository_dedup_lookup(self) -> None:
        self._seed_daily_activity()
        repo = XPEventRepository(self.db)
        self.assertIsNone(repo.find_by_dedup_key("goal_completed", "goal:1"))
        ge.process_event(self.db, "goal_completed", dedup_key="goal:1")
        self.assertIsNotNone(repo.find_by_dedup_key("goal_completed", "goal:1"))
        # The key is scoped by event_type: another type must not match.
        self.assertIsNone(repo.find_by_dedup_key("note_created", "goal:1"))


class TestRouterIdempotency:
    """HTTP-level idempotency via the shared client/db_session fixtures."""

    def _goal_completed_events(self, db_session, goal_id: int):
        return (
            db_session.query(XPEvent)
            .filter(XPEvent.event_type == "goal_completed", XPEvent.dedup_key == f"goal:{goal_id}")
            .all()
        )

    def _topic_connected_events(self, db_session, child_id: int):
        return [
            e
            for e in db_session.query(XPEvent).filter(XPEvent.event_type == "topic_connected").all()
            if (e.dedup_key or "").startswith(f"tag_parent:{child_id}:")
        ]

    def test_goal_complete_awards_xp_once(self, client: TestClient, db_session):
        """AC: repeated POST /goals/{id}/complete awards XP once."""
        title = f"Goal-{uuid4().hex[:8]}"
        goal_id = client.post(
            "/goals/",
            json={"title": title, "temporality": "DAILY", "measurement_type": "BOOLEAN"},
        ).json()["id"]

        first = client.post(f"/goals/{goal_id}/complete")
        assert first.status_code == 200
        assert first.json()["gamification"]["xp_awarded"] >= 50
        total_after_first = first.json()["gamification"]["total_xp"]

        for _ in range(2):
            replay = client.post(f"/goals/{goal_id}/complete")
            assert replay.status_code == 200
            body = replay.json()
            assert body["already_completed"] is True
            assert body["gamification"]["xp_awarded"] == 0
            assert body["gamification"]["total_xp"] == total_after_first

        assert len(self._goal_completed_events(db_session, goal_id)) == 1

    def test_reparent_toggling_does_not_farm_topic_connected(self, client: TestClient, db_session):
        """AC-adjacent: A→B→A toggling awards each (tag, parent) pair once."""
        suffix = uuid4().hex[:8]
        parent_a = client.post("/tags/", json={"name": f"parent-a-{suffix}"}).json()
        parent_b = client.post("/tags/", json={"name": f"parent-b-{suffix}"}).json()
        child = client.post("/tags/", json={"name": f"child-{suffix}"}).json()

        # A → B → A → B: only the two distinct pairs may ever be recorded.
        for parent in (parent_a, parent_b, parent_a, parent_b):
            res = client.put(f"/tags/{child['id']}/parent?parent_id={parent['id']}")
            assert res.status_code == 200

        events = self._topic_connected_events(db_session, child["id"])
        assert len(events) == 2
        assert {e.dedup_key for e in events} == {
            f"tag_parent:{child['id']}:{parent_a['id']}",
            f"tag_parent:{child['id']}:{parent_b['id']}",
        }
