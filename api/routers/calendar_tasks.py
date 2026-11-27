"""CRUD for internal joidy calendar tasks (#1230).

Planning suite (#1658): tasks gained full event-editor fields
(description/location/attendees/note_id), a duplicate endpoint, and a
``/calendar/day-metrics`` aggregation feeding the per-day intelligence
badges (focus minutes, notes, XP, goals, mood, streak).
"""

import json
from calendar import monthrange
from datetime import UTC, datetime, time, timedelta
from datetime import date as date_type
from typing import cast

from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from models.calendar_task import (
    CalendarTask,
    CalendarTaskPriority,
    CalendarTaskRecurrence,
    CalendarTaskSource,
)
from models.gamification import StreakRecord, XPEvent
from models.goal import Goal, GoalMeasurement
from models.mood_entry import MoodEntry
from models.note import Note
from pydantic import BaseModel, Field
from services import task_google_sync
from services.auth_service import get_current_user
from services.gamification_engine import process_event
from services.timezone_utils import get_local_today
from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload

router = APIRouter(prefix="/calendar", tags=["calendar"])

# Execution-queue ordering (#1234): URGENT first, LOW last. A CASE ranking is
# used instead of ordering the enum directly because SQLite sorts enum values
# alphabetically (MEDIUM > LOW > HIGH), which would scramble the priority.
_PRIORITY_RANK = case(
    (CalendarTask.priority == CalendarTaskPriority.URGENT, 0),
    (CalendarTask.priority == CalendarTaskPriority.HIGH, 1),
    (CalendarTask.priority == CalendarTaskPriority.MEDIUM, 2),
    (CalendarTask.priority == CalendarTaskPriority.LOW, 3),
    else_=4,
)


def _xp_event_recorded(db: Session, event_types: tuple[str, ...], dedup_key: str) -> bool:
    """True when an ``xp_events`` row already carries this idempotency key.

    Uses the indexed ``dedup_key`` column (#1320) instead of scanning and
    reparsing ``metadata_json`` blobs.
    """
    return (
        db.query(XPEvent).filter(XPEvent.event_type.in_(event_types), XPEvent.dedup_key == dedup_key).first()
        is not None
    )


def _award_task_xp(db: Session, task: CalendarTask) -> None:
    """Award XP for completing a planned task (#1235).

    Anti-double-count: a task linked to a goal only awards XP through one
    channel. Since completing the goal already fires `goal_completed` (+50),
    a linked task awards nothing — the greater XP wins. Goal progress is
    handled separately by `_adjust_goal_progress` (#1234).
    `day_fully_planned` fires when the last open task of the day is completed.

    Anti-farming (audit): each award is idempotent. Re-toggling a task
    done → undone → done must not mint XP every cycle, so a task earns its
    completion XP once (checked across both completion event types, so
    adding/removing ``start_time`` between toggles cannot mint the other
    variant either) and a day earns `day_fully_planned` once.
    """
    if task.goal_id is not None:
        return
    event = "calendar_task_completed" if task.start_time else "calendar_task_completed_no_time"
    dedup_key = f"calendar_task:{task.id}"
    already_completed = _xp_event_recorded(
        db, ("calendar_task_completed", "calendar_task_completed_no_time"), dedup_key
    )
    if not already_completed:
        process_event(
            db,
            event,
            {"task_id": task.id, "title": task.title, "date": str(task.date)},
            dedup_key=dedup_key,
        )

    if task.date is None:
        return
    # Day fully planned bonus: no open tasks left for that date.
    open_left = (
        db.query(CalendarTask)
        .filter(CalendarTask.date == task.date, CalendarTask.done.is_(False), CalendarTask.id != task.id)
        .count()
    )
    day_dedup_key = f"day_fully_planned:{task.date}"
    if open_left == 0 and not _xp_event_recorded(db, ("day_fully_planned",), day_dedup_key):
        process_event(db, "day_fully_planned", {"date": str(task.date)}, dedup_key=day_dedup_key)


def _adjust_goal_progress(db: Session, task: CalendarTask, delta: float) -> None:
    """Move the linked goal's ``current_value`` by ``delta`` (#1234).

    Called symmetrically on the done edge (+1) and on the un-done edge (−1),
    so un-completing a task never double-counts progress. Only manual COUNT
    goals are moved: tag-derived COUNT goals compute progress from tagged
    notes (see goal_service.get_goal_progress), not ``current_value``, and
    BOOLEAN/PERCENT goals have their own completion path. Goal completion
    itself is left to ``evaluate_active_goals`` / the complete endpoint.
    """
    if task.goal_id is None:
        return
    goal = db.get(Goal, task.goal_id)
    if goal is None:
        return
    if goal.measurement_type != GoalMeasurement.COUNT or goal.tag_id is not None:
        return
    goal.current_value = max(0.0, goal.current_value + delta)


def _next_date(day: date_type, recurrence: CalendarTaskRecurrence) -> date_type:
    """Advance ``day`` by one recurrence step (#1238).

    MONTHLY keeps the same day-of-month clamped to the target month's
    length (Jan 31 → Feb 28/29, which then stays on the 28th/29th — the
    clamp does not restore the original day).
    """
    if recurrence == CalendarTaskRecurrence.DAILY:
        return day + timedelta(days=1)
    if recurrence == CalendarTaskRecurrence.WEEKLY:
        return day + timedelta(days=7)
    if recurrence == CalendarTaskRecurrence.MONTHLY:
        month = day.month % 12 + 1
        year = day.year + (1 if day.month == 12 else 0)
        last_day = monthrange(year, month)[1]
        return date_type(year, month, min(day.day, last_day))
    return day


def _spawn_next_occurrence(db: Session, task: CalendarTask) -> None:
    """Create the next occurrence of a recurring task on the done edge (#1238).

    Scope: only scheduled tasks (``date`` set) that are NOT goal-linked —
    goal-linked recurring work is tracked by the goal progress paths
    (#1234) and a spawned copy would double-count it. Unscheduled tasks may
    carry a recurrence value but never spawn (no date to advance).

    The spawned row is a fresh joidy task: ``google_event_id`` is cleared
    (it is NOT auto-published to Google — write-back stays out of scope)
    and the reminder offset plus the event-editor fields (#1658) are carried
    over so the series keeps firing with its details intact. The vault-note
    backlink (``note_id``) is NOT copied — it points at the specific
    occurrence's note, not the whole series'.

    Idempotency: re-toggling a task undone → done must not mint duplicates,
    so the spawn is skipped when a same-title, same-source task already
    exists on the computed next date.
    """
    if task.recurrence == CalendarTaskRecurrence.NONE or task.date is None or task.goal_id is not None:
        return
    next_date = _next_date(task.date, task.recurrence)
    already_spawned = (
        db.query(CalendarTask)
        .filter(
            CalendarTask.title == task.title,
            CalendarTask.date == next_date,
            CalendarTask.source == task.source,
        )
        .first()
    )
    if already_spawned is not None:
        return
    db.add(
        CalendarTask(
            title=task.title,
            date=next_date,
            start_time=task.start_time,
            end_time=task.end_time,
            priority=task.priority,
            done=False,
            goal_id=None,
            source=task.source,
            google_event_id=None,
            color=task.color,
            recurrence=task.recurrence,
            reminder_minutes=task.reminder_minutes,
            description=task.description,
            location=task.location,
            attendees=task.attendees,
        )
    )


def _apply_done_transition(db: Session, task: CalendarTask, was_done: bool) -> None:
    if not was_done and task.done:
        _award_task_xp(db, task)
        _adjust_goal_progress(db, task, 1)
        _spawn_next_occurrence(db, task)
        db.commit()
    elif was_done and not task.done:
        _adjust_goal_progress(db, task, -1)
        db.commit()


class CalendarTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    # NULL date → task lands in the unscheduled queue ("sin planificar", #1234).
    date: date_type | None = None
    start_time: time | None = None
    end_time: time | None = None
    priority: CalendarTaskPriority = CalendarTaskPriority.MEDIUM
    goal_id: int | None = None
    color: str | None = Field(default=None, max_length=20)
    recurrence: CalendarTaskRecurrence = CalendarTaskRecurrence.NONE
    # Minutes before start_time; NULL = no reminder. Capped at one day.
    reminder_minutes: int | None = Field(default=None, ge=0, le=1440)
    # Event-editor fields (#1658).
    description: str | None = Field(default=None, max_length=5000)
    location: str | None = Field(default=None, max_length=500)
    # Comma-separated attendee e-mails; passed through to Google on publish.
    attendees: str | None = Field(default=None, max_length=2000)


class CalendarTaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    date: date_type | None = None
    start_time: time | None = None
    end_time: time | None = None
    priority: CalendarTaskPriority | None = None
    done: bool | None = None
    goal_id: int | None = None
    color: str | None = Field(default=None, max_length=20)
    recurrence: CalendarTaskRecurrence | None = None
    reminder_minutes: int | None = Field(default=None, ge=0, le=1440)
    # Write-back mirror (#1233): set by the frontend after creating the
    # Google event, so later edits/deletes can propagate to Google.
    google_event_id: str | None = Field(default=None, max_length=255)
    # Event-editor fields (#1658).
    description: str | None = Field(default=None, max_length=5000)
    location: str | None = Field(default=None, max_length=500)
    attendees: str | None = Field(default=None, max_length=2000)
    # Vault-note backlink — set by the frontend after quick-capture (#1658).
    note_id: int | None = None


class CalendarTaskOut(BaseModel):
    id: int
    title: str
    date: date_type | None
    start_time: time | None
    end_time: time | None
    priority: CalendarTaskPriority
    done: bool
    done_at: datetime | None
    goal_id: int | None
    # Title of the linked goal, when set — lets UIs show the planning link
    # without a second fetch (#goal-planning-calendar).
    goal_title: str | None = None
    source: CalendarTaskSource
    google_event_id: str | None
    color: str | None
    recurrence: CalendarTaskRecurrence
    reminder_minutes: int | None
    description: str | None
    location: str | None
    attendees: str | None
    note_id: int | None
    created_at: datetime
    updated_at: datetime


def _parse_date(value: str) -> date_type:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")


def _validate_times(start_time: time | None, end_time: time | None) -> None:
    if start_time and end_time and end_time <= start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")


def _task_out(task: CalendarTask) -> CalendarTaskOut:
    # SQLAlchemy `Time` columns are typed as datetime|None by the ORM stubs;
    # at runtime they always hold datetime.time.
    return CalendarTaskOut(
        id=task.id,
        title=task.title,
        date=task.date,
        start_time=cast("time | None", task.start_time),
        end_time=cast("time | None", task.end_time),
        priority=task.priority,
        done=task.done,
        done_at=task.done_at,
        goal_id=task.goal_id,
        goal_title=task.goal.title if task.goal is not None else None,
        source=task.source,
        google_event_id=task.google_event_id,
        color=task.color,
        recurrence=task.recurrence,
        reminder_minutes=task.reminder_minutes,
        description=task.description,
        location=task.location,
        attendees=task.attendees,
        note_id=task.note_id,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _get_or_404(db: Session, task_id: int) -> CalendarTask:
    task = db.query(CalendarTask).filter(CalendarTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Calendar task not found")
    return cast(CalendarTask, task)


@router.get("/tasks", response_model=list[CalendarTaskOut])
def list_tasks(
    start: str | None = None,
    end: str | None = None,
    date: str | None = None,
    unscheduled: bool = False,
    db: Session = Depends(get_db),
):
    query = db.query(CalendarTask)
    if unscheduled:
        query = query.filter(CalendarTask.date.is_(None))
    elif date or start or end:
        # Unscheduled tasks (date IS NULL) never belong to a date/range filter.
        query = query.filter(CalendarTask.date.isnot(None))
    if date:
        query = query.filter(CalendarTask.date == _parse_date(date))
    if start:
        query = query.filter(CalendarTask.date >= _parse_date(start))
    if end:
        query = query.filter(CalendarTask.date <= _parse_date(end))
    query = query.order_by(CalendarTask.date.asc(), CalendarTask.start_time.asc().nullslast(), CalendarTask.id.asc())
    # joinedload: _task_out reads task.goal.title for goal_title — avoids an
    # N+1 on range listings (#goal-planning-calendar).
    return [_task_out(t) for t in query.options(joinedload(CalendarTask.goal)).all()]


@router.get("/tasks/execution-queue", response_model=list[CalendarTaskOut])
def execution_queue(date: str | None = None, db: Session = Depends(get_db)):
    """Open tasks for ``date`` (default: today) in execution order (#1234).

    Ordering: priority URGENT > HIGH > MEDIUM > LOW, then start_time
    (timeless tasks last), then created_at. Consumed by the Modo Ejecución
    view (#1201).
    """
    day = _parse_date(date) if date else get_local_today()
    tasks = (
        db.query(CalendarTask)
        .filter(CalendarTask.date == day, CalendarTask.done.is_(False))
        .order_by(
            _PRIORITY_RANK,
            CalendarTask.start_time.asc().nullslast(),
            CalendarTask.created_at.asc(),
        )
        .options(joinedload(CalendarTask.goal))
        .all()
    )
    return [_task_out(t) for t in tasks]


@router.post("/tasks", response_model=CalendarTaskOut, status_code=201)
def create_task(body: CalendarTaskCreate, db: Session = Depends(get_db)):
    _validate_times(body.start_time, body.end_time)
    if body.goal_id is not None and not db.get(Goal, body.goal_id):
        raise HTTPException(status_code=404, detail="Goal not found")
    task = CalendarTask(
        title=body.title,
        date=body.date,
        start_time=body.start_time,
        end_time=body.end_time,
        priority=body.priority,
        goal_id=body.goal_id,
        color=body.color,
        recurrence=body.recurrence,
        reminder_minutes=body.reminder_minutes,
        description=body.description,
        location=body.location,
        attendees=body.attendees,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    if task.date is not None:
        task_google_sync.sync_task(db, task)
    return _task_out(task)


# Task fields whose change should re-sync the mirrored Google event.
_GOOGLE_SYNCED_FIELDS = {"title", "date", "start_time", "end_time", "color", "priority", "google_event_id"}


@router.patch("/tasks/{task_id}", response_model=CalendarTaskOut)
def update_task(task_id: int, body: CalendarTaskUpdate, db: Session = Depends(get_db)):
    task = _get_or_404(db, task_id)
    data = body.model_dump(exclude_unset=True)
    was_done = task.done
    # Fields that feed the Google mirror payload (done handled separately).
    should_sync_google = bool(set(data) & _GOOGLE_SYNCED_FIELDS)
    if "done" in data:
        task.done = data.pop("done")
        task.done_at = datetime.now(UTC) if task.done else None
    if "goal_id" in data:
        goal_id = data.pop("goal_id")
        if goal_id is not None and not db.get(Goal, goal_id):
            raise HTTPException(status_code=404, detail="Goal not found")
        task.goal_id = goal_id
    if "note_id" in data:
        note_id = data.pop("note_id")
        if note_id is not None and not db.get(Note, note_id):
            raise HTTPException(status_code=404, detail="Note not found")
        task.note_id = note_id
    for field in (
        "title",
        "date",
        "start_time",
        "end_time",
        "priority",
        "color",
        "google_event_id",
        "recurrence",
        "reminder_minutes",
        "description",
        "location",
        "attendees",
    ):
        if field in data:
            setattr(task, field, data[field])
    _validate_times(cast("time | None", task.start_time), cast("time | None", task.end_time))
    db.commit()
    db.refresh(task)
    _apply_done_transition(db, task, was_done)
    if should_sync_google or was_done != task.done:
        task_google_sync.sync_task(db, task)
    return _task_out(task)


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = _get_or_404(db, task_id)
    task_google_sync.unpublish_task(db, task)
    db.delete(task)
    db.commit()


@router.post("/tasks/{task_id}/done", response_model=CalendarTaskOut)
def toggle_done(task_id: int, db: Session = Depends(get_db)):
    task = _get_or_404(db, task_id)
    was_done = task.done
    task.done = not task.done
    task.done_at = datetime.now(UTC) if task.done else None
    db.commit()
    db.refresh(task)
    _apply_done_transition(db, task, was_done)
    if task.date is not None or task.google_event_id:
        task_google_sync.sync_task(db, task)
    return _task_out(task)


class CalendarTaskDuplicateIn(BaseModel):
    """Optional overrides applied on top of the copied fields (#1658)."""

    date: date_type | None = None
    title: str | None = Field(default=None, min_length=1, max_length=500)


@router.post("/tasks/{task_id}/duplicate", response_model=CalendarTaskOut, status_code=201)
def duplicate_task(task_id: int, body: CalendarTaskDuplicateIn | None = None, db: Session = Depends(get_db)):
    """Clone a task into a fresh JOIDY row (#1658).

    The copy is always a plain joidy task: it never carries ``google_event_id``
    (publishing the duplicate is a separate explicit action) and starts
    ``done=False`` so a completed source does not mint a pre-completed clone.
    ``date`` defaults to the source's; pass a different day to clone across
    days, or omit the body entirely.
    """
    task = _get_or_404(db, task_id)
    clone = CalendarTask(
        title=(body.title if body and body.title else task.title),
        date=(body.date if body and body.date is not None else task.date),
        start_time=task.start_time,
        end_time=task.end_time,
        priority=task.priority,
        done=False,
        goal_id=task.goal_id,
        source=CalendarTaskSource.JOIDY,
        google_event_id=None,
        color=task.color,
        recurrence=task.recurrence,
        reminder_minutes=task.reminder_minutes,
        description=task.description,
        location=task.location,
        attendees=task.attendees,
        note_id=task.note_id,
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)
    return _task_out(clone)


class DayMetrics(BaseModel):
    """Per-day intelligence badges for the planning suite (#1658).

    ``focus_minutes`` sums the pomodoro durations recorded in
    ``pomodoro_completed`` XP-event metadata; ``streak_day`` marks days that
    count toward the activity streak (a streak_records row exists).
    """

    date: date_type
    xp: int = 0
    xp_events: int = 0
    pomodoros: int = 0
    focus_minutes: int = 0
    notes: int = 0
    goals_completed: int = 0
    mood_score: int | None = None
    streak_day: bool = False


def _pomodoro_focus_minutes(db: Session, start: date_type, end: date_type) -> dict[str, int]:
    """Sum pomodoro durations per UTC day from XP-event metadata.

    ``duration_minutes`` lives inside ``metadata_json`` (JSON text), which has
    no portable SQL extraction across SQLite/Postgres, so rows are parsed in
    Python — the window is capped at 370 days and the events per day are few.
    """
    start_dt = datetime.combine(start, time.min, tzinfo=UTC)
    end_dt = datetime.combine(end, time.max, tzinfo=UTC)
    rows = (
        db.query(func.date(XPEvent.created_at).label("d"), XPEvent.metadata_json)
        .filter(
            XPEvent.event_type == "pomodoro_completed",
            XPEvent.created_at >= start_dt,
            XPEvent.created_at <= end_dt,
        )
        .all()
    )
    minutes: dict[str, int] = {}
    for row in rows:
        try:
            meta = json.loads(row.metadata_json or "{}")
            duration = int(meta.get("duration_minutes") or 0)
        except (ValueError, TypeError):
            duration = 0
        day = str(row.d)[:10]
        minutes[day] = minutes.get(day, 0) + duration
    return minutes


@router.get("/day-metrics", response_model=list[DayMetrics])
def day_metrics(
    start: str,
    end: str,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    """Aggregate per-day Joidy metrics over ``[start, end]`` (#1658).

    Sources: ``xp_events`` (XP + goals + pomodoro count), ``notes`` (created),
    ``mood_entries`` (score), ``streak_records`` (active-day flag). Dates are
    grouped on the stored day (UTC for timestamps — same convention as the
    analytics service); the window is capped at 370 days — the year view is
    the largest legitimate consumer (a full year of density dots).
    """
    start_day = _parse_date(start)
    end_day = _parse_date(end)
    if end_day < start_day:
        raise HTTPException(status_code=400, detail="end must be on or after start")
    if (end_day - start_day).days > 370:
        raise HTTPException(status_code=400, detail="Range too large (max 370 days)")

    start_dt = datetime.combine(start_day, time.min, tzinfo=UTC)
    end_dt = datetime.combine(end_day, time.max, tzinfo=UTC)

    xp_rows = (
        db.query(
            func.date(XPEvent.created_at).label("d"),
            func.coalesce(func.sum(XPEvent.xp), 0).label("xp"),
            func.count(XPEvent.id).label("events"),
            func.coalesce(func.sum(case((XPEvent.event_type == "pomodoro_completed", 1), else_=0)), 0).label(
                "pomodoros"
            ),
            func.coalesce(func.sum(case((XPEvent.event_type == "goal_completed", 1), else_=0)), 0).label(
                "goals_completed"
            ),
        )
        .filter(XPEvent.created_at >= start_dt, XPEvent.created_at <= end_dt)
        .group_by(func.date(XPEvent.created_at))
        .all()
    )
    xp_by_day = {str(r.d)[:10]: r for r in xp_rows}

    notes_rows = (
        db.query(func.date(Note.created_at).label("d"), func.count(Note.id).label("c"))
        .filter(Note.created_at >= start_dt, Note.created_at <= end_dt)
        .group_by(func.date(Note.created_at))
        .all()
    )
    notes_by_day = {str(r.d)[:10]: int(r.c) for r in notes_rows}

    mood_rows = (
        db.query(MoodEntry.entry_date, MoodEntry.score)
        .filter(
            MoodEntry.user_id == user_id,
            MoodEntry.entry_date >= start_day,
            MoodEntry.entry_date <= end_day,
        )
        .all()
    )
    mood_by_day = {r.entry_date.isoformat(): r.score for r in mood_rows}

    streak_rows = (
        db.query(StreakRecord.activity_date)
        .filter(StreakRecord.activity_date >= start_day, StreakRecord.activity_date <= end_day)
        .all()
    )
    streak_days = {r.activity_date.isoformat() for r in streak_rows}

    focus_by_day = _pomodoro_focus_minutes(db, start_day, end_day)

    metrics: list[DayMetrics] = []
    cursor = start_day
    while cursor <= end_day:
        key = cursor.isoformat()
        xp_row = xp_by_day.get(key)
        metrics.append(
            DayMetrics(
                date=cursor,
                xp=int(xp_row.xp) if xp_row else 0,
                xp_events=int(xp_row.events) if xp_row else 0,
                pomodoros=int(xp_row.pomodoros) if xp_row else 0,
                focus_minutes=focus_by_day.get(key, 0),
                notes=notes_by_day.get(key, 0),
                goals_completed=int(xp_row.goals_completed) if xp_row else 0,
                mood_score=mood_by_day.get(key),
                streak_day=key in streak_days,
            )
        )
        cursor += timedelta(days=1)
    return metrics
