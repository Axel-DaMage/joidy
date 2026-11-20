"""Tests for calendar task XP events (#1235): calendar_task_completed,
calendar_task_completed_no_time, day_fully_planned, and the anti-double-count
with goal-linked tasks."""

import datetime as dt
import sys
import types
import unittest

if "sqlite_vec" not in sys.modules:
    _stub = types.ModuleType("sqlite_vec")
    _stub.load = lambda _conn: None  # type: ignore
    sys.modules["sqlite_vec"] = _stub

from database import Base
from models.calendar_task import CalendarTask
from models.gamification import XPEvent
from services import gamification_engine as ge
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class CalendarTaskXPTestBase(unittest.TestCase):
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
        """Pre-seed today's activity so daily_activity bonus is not added."""
        stats = ge._get_or_create_stats(self.db)
        stats.last_activity_date = ge._today_utc()
        self.db.commit()

    def _xp_events(self, event_type: str) -> list[XPEvent]:
        events: list[XPEvent] = self.db.query(XPEvent).filter(XPEvent.event_type == event_type).all()
        return events


class TaskXPEventTest(CalendarTaskXPTestBase):
    def test_task_with_time_awards_5(self) -> None:
        self._seed_daily_activity()
        task = CalendarTask(title="Con hora", date=dt.date(2099, 7, 20), start_time=dt.time(10, 0))
        self.db.add(task)
        self.db.commit()

        from routers.calendar_tasks import _award_task_xp

        _award_task_xp(self.db, task)
        self.db.commit()

        events = self._xp_events("calendar_task_completed")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].xp, 5)
        self.assertEqual(self._xp_events("calendar_task_completed_no_time"), [])

    def test_task_without_time_awards_3(self) -> None:
        self._seed_daily_activity()
        task = CalendarTask(title="Sin hora", date=dt.date(2099, 7, 20))
        self.db.add(task)
        self.db.commit()

        from routers.calendar_tasks import _award_task_xp

        _award_task_xp(self.db, task)
        self.db.commit()

        events = self._xp_events("calendar_task_completed_no_time")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].xp, 3)

    def test_goal_linked_task_awards_nothing(self) -> None:
        self._seed_daily_activity()
        task = CalendarTask(title="Vinculada", date=dt.date(2099, 7, 20), goal_id=1)
        self.db.add(task)
        self.db.commit()

        from routers.calendar_tasks import _award_task_xp

        _award_task_xp(self.db, task)
        self.db.commit()

        self.assertEqual(self._xp_events("calendar_task_completed"), [])
        self.assertEqual(self._xp_events("calendar_task_completed_no_time"), [])
        self.assertEqual(self._xp_events("day_fully_planned"), [])

    def test_last_task_of_day_awards_fully_planned_bonus(self) -> None:
        self._seed_daily_activity()
        other = CalendarTask(title="Ya hecha", date=dt.date(2099, 7, 20), done=True)
        task = CalendarTask(title="Última", date=dt.date(2099, 7, 20), start_time=dt.time(9, 0))
        self.db.add_all([other, task])
        self.db.commit()

        from routers.calendar_tasks import _award_task_xp

        _award_task_xp(self.db, task)
        self.db.commit()

        self.assertEqual(len(self._xp_events("calendar_task_completed")), 1)
        bonus = self._xp_events("day_fully_planned")
        self.assertEqual(len(bonus), 1)
        self.assertEqual(bonus[0].xp, 15)

    def test_not_last_task_no_fully_planned_bonus(self) -> None:
        self._seed_daily_activity()
        pending = CalendarTask(title="Pendiente", date=dt.date(2099, 7, 20))
        task = CalendarTask(title="Hecha", date=dt.date(2099, 7, 20), start_time=dt.time(9, 0))
        self.db.add_all([pending, task])
        self.db.commit()

        from routers.calendar_tasks import _award_task_xp

        _award_task_xp(self.db, task)
        self.db.commit()

        self.assertEqual(self._xp_events("day_fully_planned"), [])

    # ── Anti-farming idempotency (audit): done → undone → done must not
    #    re-award. `_award_task_xp` is only called on a completion edge, so
    #    calling it twice models the re-toggle. ──────────────────────────

    def test_second_completion_edge_does_not_reaward(self) -> None:
        self._seed_daily_activity()
        task = CalendarTask(title="Farm", date=dt.date(2099, 7, 20), start_time=dt.time(10, 0))
        self.db.add(task)
        self.db.commit()

        from routers.calendar_tasks import _award_task_xp

        _award_task_xp(self.db, task)
        self.db.commit()
        _award_task_xp(self.db, task)
        self.db.commit()

        self.assertEqual(len(self._xp_events("calendar_task_completed")), 1)
        self.assertEqual(len(self._xp_events("day_fully_planned")), 1)

    def test_retoggle_without_time_does_not_reaward(self) -> None:
        self._seed_daily_activity()
        task = CalendarTask(title="Farm sin hora", date=dt.date(2099, 7, 20))
        self.db.add(task)
        self.db.commit()

        from routers.calendar_tasks import _award_task_xp

        _award_task_xp(self.db, task)
        self.db.commit()
        _award_task_xp(self.db, task)
        self.db.commit()

        self.assertEqual(len(self._xp_events("calendar_task_completed_no_time")), 1)
        self.assertEqual(len(self._xp_events("day_fully_planned")), 1)

    def test_adding_time_between_toggles_mints_no_second_award(self) -> None:
        """Completing once timeless then once timed must not award both."""
        self._seed_daily_activity()
        task = CalendarTask(title="Farm", date=dt.date(2099, 7, 20))
        self.db.add(task)
        self.db.commit()

        from routers.calendar_tasks import _award_task_xp

        _award_task_xp(self.db, task)
        task.start_time = dt.time(10, 0)
        self.db.commit()
        _award_task_xp(self.db, task)
        self.db.commit()

        self.assertEqual(len(self._xp_events("calendar_task_completed_no_time")), 1)
        self.assertEqual(self._xp_events("calendar_task_completed"), [])

    def test_fully_planned_bonus_once_per_date(self) -> None:
        """A re-completed task re-triggers the open_left == 0 check — the
        day's bonus must still have been recorded only once."""
        self._seed_daily_activity()
        day = dt.date(2099, 7, 20)
        a = CalendarTask(title="A", date=day)
        b = CalendarTask(title="B", date=day)
        self.db.add_all([a, b])
        self.db.commit()

        from routers.calendar_tasks import _award_task_xp

        # Both complete in turn; the second completion awards the bonus.
        a.done = True
        _award_task_xp(self.db, a)
        b.done = True
        _award_task_xp(self.db, b)
        self.db.commit()
        self.assertEqual(len(self._xp_events("day_fully_planned")), 1)

        # b is re-opened and re-completed: its own XP is idempotent and the
        # day bonus for `day` was already recorded.
        _award_task_xp(self.db, b)
        self.db.commit()

        self.assertEqual(len(self._xp_events("calendar_task_completed_no_time")), 2)
        self.assertEqual(len(self._xp_events("day_fully_planned")), 1)


class XPTableTest(CalendarTaskXPTestBase):
    def test_new_events_in_default_table(self) -> None:
        self.assertEqual(ge.xp_for("calendar_task_completed", self.db, 0), 5)
        self.assertEqual(ge.xp_for("calendar_task_completed_no_time", self.db, 0), 3)
        self.assertEqual(ge.xp_for("day_fully_planned", self.db, 0), 15)
