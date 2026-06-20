"""Unit tests for goal_service — goal parsing, sync, failure handling, streaks."""

import os
import sys
import types
import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Stub sqlite_vec before importing any app modules
if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

from database import Base
from models.goal import Goal, GoalTemporality, GoalMeasurement, GoalState, GoalFailConfig
from models.note import Note, NoteTag, Tag
from models.gamification import UserStats, XPEvent, StreakRecord
from models.skill import Skill
from services.goal_service import (
    parse_goals_from_content,
    sync_goals_from_note,
    resolve_pending_removal,
    get_goal_progress,
    get_goal_streak,
)


class GoalServiceTestBase(unittest.TestCase):
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

    def tearDown(self) -> None:
        self.engine.dispose()


class TestParseGoalsFromContent(unittest.TestCase):
    def test_parses_simple_goal(self) -> None:
        content = "# Objetivo: Leer 5 páginas @diario"
        goals = parse_goals_from_content(content)
        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0]["title"], "Leer 5 páginas")
        self.assertEqual(goals[0]["temporality"], GoalTemporality.DAILY)
        self.assertAlmostEqual(goals[0]["target_value"], 5.0)
        self.assertEqual(goals[0]["measurement_type"], GoalMeasurement.COUNT)

    def test_parses_weekly_with_fail_config(self) -> None:
        content = "# Objetivo: Escribir 3 artículos @semanal %rollover"
        goals = parse_goals_from_content(content)
        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0]["temporality"], GoalTemporality.WEEKLY)
        self.assertEqual(goals[0]["fail_config"], GoalFailConfig.ROLLOVER)

    def test_parses_boolean_goal(self) -> None:
        content = "# Objetivo: Meditar @diario"
        goals = parse_goals_from_content(content)
        self.assertEqual(len(goals), 1)
        self.assertAlmostEqual(goals[0]["target_value"], 1.0)
        self.assertEqual(goals[0]["measurement_type"], GoalMeasurement.BOOLEAN)

    def test_parses_multiple_goals(self) -> None:
        content = """
# Objetivo: Correr 5 km @diario
# Objetivo: Leer 2 libros @mensual
Some other text here
# Objetivo: Aprender guitarra @semanal
        """
        goals = parse_goals_from_content(content)
        self.assertEqual(len(goals), 3)

    def test_no_goals_in_content(self) -> None:
        content = "Just a regular note without goals."
        goals = parse_goals_from_content(content)
        self.assertEqual(len(goals), 0)

    def test_default_temporality(self) -> None:
        content = "# Objetivo: Hacer ejercicio"
        goals = parse_goals_from_content(content)
        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0]["temporality"], GoalTemporality.DAILY)


class TestSyncGoalsFromNote(GoalServiceTestBase):
    def test_creates_goals_from_note_content(self) -> None:
        with self.Session() as db:
            note = Note(title="Goals", content="# Objetivo: Test 3 items @diario", source="joidy")
            db.add(note)
            db.flush()

            sync_goals_from_note(db, note.id, note.content)
            db.commit()

            goals = db.query(Goal).filter(Goal.note_id == note.id).all()
            self.assertEqual(len(goals), 1)
            self.assertEqual(goals[0].title, "Test 3 items")

    def test_marks_removed_goals_as_pending(self) -> None:
        with self.Session() as db:
            note = Note(title="Goals", content="", source="joidy")
            db.add(note)
            db.flush()

            goal = Goal(
                title="Old Goal", note_id=note.id,
                state=GoalState.ACTIVE, temporality=GoalTemporality.DAILY,
            )
            db.add(goal)
            db.flush()

            # Sync with content that doesn't contain the goal
            sync_goals_from_note(db, note.id, "No goals here")
            db.commit()

            db.refresh(goal)
            self.assertTrue(goal.pending_removal)

    def test_updates_existing_goal(self) -> None:
        with self.Session() as db:
            note = Note(title="G", content="", source="joidy")
            db.add(note)
            db.flush()

            goal = Goal(
                title="Leer 5 páginas", note_id=note.id,
                state=GoalState.ACTIVE, temporality=GoalTemporality.DAILY,
                target_value=5.0,
            )
            db.add(goal)
            db.flush()

            new_content = "# Objetivo: Leer 5 páginas @semanal"
            sync_goals_from_note(db, note.id, new_content)
            db.commit()

            db.refresh(goal)
            self.assertEqual(goal.temporality, GoalTemporality.WEEKLY)


class TestResolveRemoval(GoalServiceTestBase):
    def _create_pending_goal(self, db):
        goal = Goal(
            title="Pending", state=GoalState.ACTIVE,
            temporality=GoalTemporality.DAILY, pending_removal=True,
        )
        db.add(goal)
        db.flush()
        return goal

    def test_delete_action(self) -> None:
        with self.Session() as db:
            goal = self._create_pending_goal(db)
            goal_id = goal.id
            result = resolve_pending_removal(db, goal_id, "delete")
            db.commit()
            self.assertIsNone(result)
            self.assertIsNone(db.query(Goal).filter(Goal.id == goal_id).first())

    def test_cancel_action(self) -> None:
        with self.Session() as db:
            goal = self._create_pending_goal(db)
            result = resolve_pending_removal(db, goal.id, "cancel")
            db.commit()
            self.assertEqual(result.state, GoalState.CANCELLED)
            self.assertFalse(result.pending_removal)

    def test_manual_action_unlinks_note(self) -> None:
        with self.Session() as db:
            note = Note(title="N", content="", source="joidy")
            db.add(note)
            db.flush()

            goal = Goal(
                title="Manual", state=GoalState.ACTIVE,
                temporality=GoalTemporality.DAILY,
                pending_removal=True, note_id=note.id,
            )
            db.add(goal)
            db.flush()

            result = resolve_pending_removal(db, goal.id, "manual")
            db.commit()
            self.assertIsNone(result.note_id)


class TestGetGoalStreak(GoalServiceTestBase):
    def test_empty_streak(self) -> None:
        with self.Session() as db:
            result = get_goal_streak(db)
            self.assertEqual(result["current_streak"], 0)
            self.assertEqual(result["best_streak"], 0)

    def test_consecutive_days(self) -> None:
        with self.Session() as db:
            today = datetime.utcnow()
            for i in range(3):
                g = Goal(
                    title=f"G{i}", state=GoalState.COMPLETED,
                    temporality=GoalTemporality.DAILY,
                    is_completed=True,
                    completed_at=today - timedelta(days=i),
                )
                db.add(g)
            db.commit()

            result = get_goal_streak(db)
            self.assertEqual(result["current_streak"], 3)
            self.assertEqual(result["best_streak"], 3)


if __name__ == "__main__":
    unittest.main()
