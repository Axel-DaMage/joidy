"""Unit tests for mood_service — create/update (upsert), get today, history, and stats.

Uses in-memory SQLite and stubs sqlite_vec (matches conftest pattern).
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
from models.mood_entry import MoodEntry
from services.mood_service import (
    create_or_update_mood,
    get_mood_history,
    get_mood_stats,
    get_today_mood,
)
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


class MoodServiceTestBase(unittest.TestCase):
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

    def _today(self) -> date:
        return datetime.now(UTC).date()


class CreateOrUpdateMoodTest(MoodServiceTestBase):
    def test_create_today_mood(self):
        db = self.Session()
        entry = create_or_update_mood(db, user_id=1, score=4, note="Good day")
        self.assertEqual(entry.score, 4)
        self.assertEqual(entry.note, "Good day")
        self.assertEqual(entry.entry_date, self._today())
        self.assertEqual(entry.user_id, 1)
        db.close()

    def test_update_today_mood_upsert(self):
        db = self.Session()
        create_or_update_mood(db, user_id=1, score=3)
        # Second call on the same day should update, not create a new entry.
        entry = create_or_update_mood(db, user_id=1, score=5, note="Great!")
        self.assertEqual(entry.score, 5)
        self.assertEqual(entry.note, "Great!")
        # Only one entry for today.
        count = db.query(MoodEntry).filter(MoodEntry.user_id == 1, MoodEntry.entry_date == self._today()).count()
        self.assertEqual(count, 1)
        db.close()

    def test_different_users_separate_entries(self):
        db = self.Session()
        create_or_update_mood(db, user_id=1, score=2)
        create_or_update_mood(db, user_id=2, score=5)
        e1 = get_today_mood(db, user_id=1)
        e2 = get_today_mood(db, user_id=2)
        self.assertEqual(e1.score, 2)
        self.assertEqual(e2.score, 5)
        db.close()


class GetTodayMoodTest(MoodServiceTestBase):
    def test_no_entry_returns_none(self):
        db = self.Session()
        result = get_today_mood(db, user_id=1)
        self.assertIsNone(result)
        db.close()

    def test_returns_entry_after_creation(self):
        db = self.Session()
        create_or_update_mood(db, user_id=1, score=3)
        entry = get_today_mood(db, user_id=1)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.score, 3)
        db.close()


class GetMoodHistoryTest(MoodServiceTestBase):
    def test_empty_history(self):
        db = self.Session()
        history = get_mood_history(db, user_id=1, days=7)
        self.assertEqual(len(history), 0)
        db.close()

    def test_history_returns_entries_in_range(self):
        db = self.Session()
        today = self._today()
        # Create entries for today and 3 days ago.
        db.add(MoodEntry(user_id=1, score=4, entry_date=today))
        db.add(MoodEntry(user_id=1, score=2, entry_date=today - timedelta(days=3)))
        db.commit()
        history = get_mood_history(db, user_id=1, days=7)
        self.assertEqual(len(history), 2)
        # Ordered oldest → newest.
        self.assertEqual(history[0].entry_date, today - timedelta(days=3))
        self.assertEqual(history[1].entry_date, today)
        db.close()

    def test_history_excludes_old_entries(self):
        db = self.Session()
        today = self._today()
        db.add(MoodEntry(user_id=1, score=4, entry_date=today))
        db.add(MoodEntry(user_id=1, score=1, entry_date=today - timedelta(days=10)))
        db.commit()
        history = get_mood_history(db, user_id=1, days=7)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].entry_date, today)
        db.close()

    def test_history_days_clamped(self):
        db = self.Session()
        # days < 1 should be clamped to 1, days > 366 to 366 — no crash.
        history = get_mood_history(db, user_id=1, days=0)
        self.assertEqual(len(history), 0)
        history = get_mood_history(db, user_id=1, days=999)
        self.assertEqual(len(history), 0)
        db.close()


class GetMoodStatsTest(MoodServiceTestBase):
    def test_no_entries_returns_zeros(self):
        db = self.Session()
        stats = get_mood_stats(db, user_id=1)
        self.assertEqual(stats["average"], 0.0)
        self.assertEqual(stats["streak"], 0)
        self.assertEqual(stats["total_entries"], 0)
        self.assertEqual(stats["notes_correlation"], 0.0)
        db.close()

    def test_average_score(self):
        db = self.Session()
        today = self._today()
        db.add(MoodEntry(user_id=1, score=3, entry_date=today))
        db.add(MoodEntry(user_id=1, score=5, entry_date=today - timedelta(days=1)))
        db.commit()
        stats = get_mood_stats(db, user_id=1)
        self.assertEqual(stats["average"], 4.0)
        self.assertEqual(stats["total_entries"], 2)
        db.close()

    def test_streak_consecutive_days(self):
        db = self.Session()
        today = self._today()
        for i in range(3):
            db.add(MoodEntry(user_id=1, score=4, entry_date=today - timedelta(days=i)))
        db.commit()
        stats = get_mood_stats(db, user_id=1)
        self.assertEqual(stats["streak"], 3)
        db.close()

    def test_streak_broken_by_gap(self):
        db = self.Session()
        today = self._today()
        # Today and 2 days ago, but not yesterday — streak is 1.
        db.add(MoodEntry(user_id=1, score=4, entry_date=today))
        db.add(MoodEntry(user_id=1, score=3, entry_date=today - timedelta(days=2)))
        db.commit()
        stats = get_mood_stats(db, user_id=1)
        self.assertEqual(stats["streak"], 1)
        db.close()

    def test_streak_counts_yesterday_if_no_today(self):
        db = self.Session()
        yesterday = self._today() - timedelta(days=1)
        db.add(MoodEntry(user_id=1, score=4, entry_date=yesterday))
        db.commit()
        stats = get_mood_stats(db, user_id=1)
        self.assertEqual(stats["streak"], 1)
        db.close()

    def test_notes_correlation(self):
        db = self.Session()
        today = self._today()
        db.add(MoodEntry(user_id=1, score=4, entry_date=today, note="Good"))
        db.add(MoodEntry(user_id=1, score=2, entry_date=today - timedelta(days=1), note=None))
        db.commit()
        stats = get_mood_stats(db, user_id=1)
        # 1 of 2 entries has a note → 0.5
        self.assertEqual(stats["notes_correlation"], 0.5)
        db.close()


if __name__ == "__main__":
    unittest.main()
