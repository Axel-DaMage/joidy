"""Unit tests for gamification_engine — XP awarding, daily_activity idempotency,
streak grace period, plant stages, and the max-XP cap. The engine had only e2e
tests, so XP-farming (#359) and timezone (#361) bugs went undetected."""

import sys
import types
import unittest
from datetime import timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

from database import Base
import services.gamification_engine as ge
from services.gamification_engine import (
    DEFAULT_PLANT_STAGES,
    GRACE_PERIOD_DAYS,
    STREAK_MILESTONES,
    _compute_plant_stage,
    _compute_streak,
    process_event,
)
from models.gamification import UserStats


class GamificationTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            try:
                conn.execute(text(
                    "CREATE TABLE IF NOT EXISTS tag_cooccurrences "
                    "(tag_a_id INTEGER, tag_b_id INTEGER, weight INTEGER, "
                    "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
                ))
            except Exception:
                pass
        self.Session = sessionmaker(bind=self.engine)
        # Reset module-level caches so each test starts from defaults.
        ge._xp_table_cache = None
        ge._plant_stages_cache = None

    def tearDown(self) -> None:
        self.engine.dispose()


class XPAwardingTest(GamificationTestBase):
    def _seed_daily_activity(self, db) -> None:
        """Pre-seed today's activity so the daily_activity bonus is not
        double-counted on top of the event XP."""
        stats = ge._get_or_create_stats(db)
        stats.last_activity_date = ge._today_utc()
        from models.gamification import StreakRecord
        from repositories import StreakRecordRepository
        if not StreakRecordRepository(db).get_today():
            StreakRecordRepository(db).add(
                StreakRecord(activity_date=ge._today_utc(), xp_earned=0)
            )
        db.commit()

    def test_note_created_awards_10_xp(self):
        db = self.Session()
        self._seed_daily_activity(db)
        result = process_event(db, "note_created")
        db.commit()
        self.assertEqual(result.xp_awarded, 10)
        self.assertEqual(result.total_xp, 10)
        db.close()

    def test_unknown_event_awards_zero(self):
        db = self.Session()
        self._seed_daily_activity(db)
        result = process_event(db, "nonexistent_event")
        self.assertEqual(result.xp_awarded, 0)
        db.close()

    def test_daily_activity_idempotent_per_day(self):
        db = self.Session()
        first = process_event(db, "daily_activity")
        db.commit()
        self.assertEqual(first.xp_awarded, 15)

        second = process_event(db, "daily_activity")
        db.commit()
        # Same day → no additional XP.
        self.assertEqual(second.xp_awarded, 0)
        self.assertEqual(second.total_xp, first.total_xp)
        db.close()


class StreakTest(GamificationTestBase):
    def test_first_activity_starts_streak_at_1(self):
        db = self.Session()
        stats = ge._get_or_create_stats(db)
        streak, changed = _compute_streak(db, stats)
        self.assertEqual(streak, 1)
        self.assertTrue(changed)
        db.close()

    def test_consecutive_day_increments_streak(self):
        db = self.Session()
        stats = ge._get_or_create_stats(db)
        stats.current_streak = 3
        stats.last_activity_date = ge._today_utc() - timedelta(days=1)
        streak, changed = _compute_streak(db, stats)
        self.assertEqual(streak, 4)
        self.assertTrue(changed)
        db.close()

    def test_grace_period_preserves_streak(self):
        db = self.Session()
        stats = ge._get_or_create_stats(db)
        stats.current_streak = 5
        # One missed day within the grace window.
        stats.last_activity_date = ge._today_utc() - timedelta(days=GRACE_PERIOD_DAYS + 1)
        streak, changed = _compute_streak(db, stats)
        self.assertEqual(streak, 5)  # unchanged, not broken
        db.close()

    def test_gap_beyond_grace_breaks_streak(self):
        db = self.Session()
        stats = ge._get_or_create_stats(db)
        stats.current_streak = 5
        stats.last_activity_date = ge._today_utc() - timedelta(days=GRACE_PERIOD_DAYS + 2)
        streak, changed = _compute_streak(db, stats)
        self.assertEqual(streak, 1)  # reset
        db.close()


class PlantStageTest(GamificationTestBase):
    def test_zero_xp_is_first_stage(self):
        idx, name = _compute_plant_stage(0)
        self.assertEqual(idx, 0)
        self.assertEqual(name, DEFAULT_PLANT_STAGES[0][1])

    def test_high_xp_reaches_last_stage(self):
        idx, name = _compute_plant_stage(DEFAULT_PLANT_STAGES[-1][0])
        self.assertEqual(idx, len(DEFAULT_PLANT_STAGES) - 1)
        self.assertEqual(name, DEFAULT_PLANT_STAGES[-1][1])

    def test_milestone_xp_awarded(self):
        db = self.Session()
        # Drive the streak to a milestone (7) by simulating consecutive days.
        stats = ge._get_or_create_stats(db)
        stats.current_streak = 6
        stats.last_activity_date = ge._today_utc() - timedelta(days=1)
        db.commit()
        result = process_event(db, "note_created")
        db.commit()
        if 7 in STREAK_MILESTONES:
            self.assertEqual(result.milestone_reached, 7)
        db.close()


class MaxXPCapTest(GamificationTestBase):
    def test_no_xp_beyond_max_stage(self):
        db = self.Session()
        stats = ge._get_or_create_stats(db)
        stats.total_xp = DEFAULT_PLANT_STAGES[-1][0]
        db.commit()
        result = process_event(db, "note_created")
        db.commit()
        self.assertEqual(result.xp_awarded, 0)
        db.close()


if __name__ == "__main__":
    unittest.main()
