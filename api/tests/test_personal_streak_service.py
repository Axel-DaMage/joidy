"""Unit tests for personal_streak_service — streak creation, check-in increment,
streak breaking (missed days), and grace period / every_n frequency logic.

Uses in-memory SQLite and the real repository layer to exercise
compute_streak and calculate_streak_stats.
"""

import sys
import types
import unittest
from datetime import UTC, date, datetime, timedelta

# Stub sqlite_vec before importing app modules (matches conftest pattern).
if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

from database import Base
from models.personal_streaks import PersonalStreak, StreakCheckIn
from repositories import PersonalStreakRepository, StreakCheckInRepository
from services.personal_streak_service import (
    backfill_streak_history,
    calculate_streak_stats,
    compute_streak,
)
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class PersonalStreakTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
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

    def _today(self) -> date:
        return datetime.now(UTC).date()

    def _create_streak(self, db, **kwargs) -> PersonalStreak:
        defaults = {
            "name": "Test Streak",
            "frequency": "daily",
            "frequency_days": 1,
        }
        defaults.update(kwargs)
        streak = PersonalStreakRepository(db).add(PersonalStreak(**defaults))
        db.commit()
        return streak

    def _add_checkin(self, db, streak, check_date) -> StreakCheckIn:
        ci = StreakCheckIn(streak_id=streak.id, check_date=check_date)
        StreakCheckInRepository(db).add(ci)
        db.commit()
        return ci


class ComputeStreakDailyTest(PersonalStreakTestBase):
    def test_empty_checkins_returns_zero(self):
        current, longest = compute_streak([])
        self.assertEqual(current, 0)
        self.assertEqual(longest, 0)

    def test_single_checkin_today(self):
        today = self._today()
        current, longest = compute_streak([today])
        self.assertEqual(current, 1)
        self.assertEqual(longest, 1)

    def test_consecutive_days_increment_streak(self):
        today = self._today()
        dates = [today - timedelta(days=i) for i in range(5)]
        current, longest = compute_streak(dates)
        self.assertEqual(current, 5)
        self.assertEqual(longest, 5)

    def test_missed_today_counts_yesterday(self):
        # If today is not checked in but yesterday is, streak counts from yesterday.
        yesterday = self._today() - timedelta(days=1)
        current, longest = compute_streak([yesterday])
        self.assertEqual(current, 1)

    def test_gap_breaks_streak(self):
        today = self._today()
        # 3 consecutive then a 3-day gap then 2 consecutive.
        dates = [today - timedelta(days=i) for i in range(2)]  # today, yesterday
        dates.append(today - timedelta(days=5))
        dates.append(today - timedelta(days=6))
        dates.append(today - timedelta(days=7))
        current, longest = compute_streak(dates)
        self.assertEqual(current, 2)  # the recent run of 2
        self.assertEqual(longest, 3)  # the older run of 3

    def test_longest_run_is_max(self):
        today = self._today()
        # Run of 2, gap, run of 4.
        dates = [today - timedelta(days=i) for i in range(4)]
        dates.append(today - timedelta(days=6))
        dates.append(today - timedelta(days=7))
        current, longest = compute_streak(dates)
        self.assertEqual(current, 4)
        self.assertEqual(longest, 4)


class ComputeStreakEveryNTest(PersonalStreakTestBase):
    def test_every_n_allows_gap_within_n(self):
        today = self._today()
        # Every 3 days: today, 3 days ago, 6 days ago.
        dates = [today, today - timedelta(days=3), today - timedelta(days=6)]
        current, longest = compute_streak(dates, frequency="every_n", frequency_days=3)
        self.assertEqual(current, 3)
        self.assertEqual(longest, 3)

    def test_every_n_gap_beyond_n_breaks(self):
        today = self._today()
        # Gap of 5 days exceeds frequency_days=3.
        dates = [today, today - timedelta(days=5)]
        current, longest = compute_streak(dates, frequency="every_n", frequency_days=3)
        self.assertEqual(current, 1)


class CalculateStreakStatsTest(PersonalStreakTestBase):
    def test_stats_reflect_checkins(self):
        db = self.Session()
        streak = self._create_streak(db)
        today = self._today()
        for i in range(3):
            self._add_checkin(db, streak, today - timedelta(days=i))

        db.refresh(streak)
        stats = calculate_streak_stats(streak)
        self.assertEqual(stats["current_streak"], 3)
        self.assertEqual(stats["longest_streak"], 3)
        db.close()

    def test_stats_with_no_checkins(self):
        db = self.Session()
        streak = self._create_streak(db)
        stats = calculate_streak_stats(streak)
        self.assertEqual(stats["current_streak"], 0)
        self.assertEqual(stats["longest_streak"], 0)
        db.close()


class BackfillStreakHistoryTest(PersonalStreakTestBase):
    def test_backfill_generates_missing_checkins(self):
        db = self.Session()
        start = self._today() - timedelta(days=5)
        streak = self._create_streak(db, start_date=start)
        # Set created_at to today so backfill covers start..yesterday.
        streak.created_at = datetime.now(UTC)
        db.commit()
        db.refresh(streak)

        backfill_streak_history(db, streak)
        db.refresh(streak)
        # Should have check-ins for start_date through yesterday (5 days).
        self.assertEqual(len(streak.checkins), 5)
        self.assertEqual(streak.total_checkins, 5)
        db.close()

    def test_backfill_no_start_date_does_nothing(self):
        db = self.Session()
        streak = self._create_streak(db)  # no start_date
        backfill_streak_history(db, streak)
        db.refresh(streak)
        self.assertEqual(len(streak.checkins), 0)
        db.close()

    def test_backfill_every_n_frequency(self):
        db = self.Session()
        start = self._today() - timedelta(days=6)
        streak = self._create_streak(db, start_date=start, frequency="every_n", frequency_days=2)
        streak.created_at = datetime.now(UTC)
        db.commit()
        db.refresh(streak)

        backfill_streak_history(db, streak)
        db.refresh(streak)
        # Every 2 days from start over 6 days: day 0, 2, 4 = 3 check-ins (excluding today).
        checkin_dates = {c.check_date for c in streak.checkins}
        expected = {start + timedelta(days=i) for i in range(0, 6, 2) if start + timedelta(days=i) < self._today()}
        self.assertEqual(checkin_dates, expected)
        db.close()


if __name__ == "__main__":
    unittest.main()
