"""CRUD for internal joidy calendar tasks (#1230)."""

import json
from datetime import UTC, datetime, time
from datetime import date as date_type
from typing import cast

from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from models.calendar_task import CalendarTask, CalendarTaskPriority, CalendarTaskSource
from models.gamification import XPEvent
from models.goal import Goal, GoalMeasurement
from pydantic import BaseModel, Field
from services.gamification_engine import process_event
from services.timezone_utils import get_local_today
from sqlalchemy import case
from sqlalchemy.orm import Session

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


def _xp_event_recorded(db: Session, event_type: str, key: str, value: object) -> bool:
    """True when an ``xp_events`` row of ``event_type`` already stores ``key: value``.

    Idempotency guard for the XP awards below: ``metadata_json`` is a
    serialized JSON blob, so a LIKE pre-filter (the ``json.dumps`` rendering
    is deterministic — these rows are only ever written by ``process_event``)
    narrows candidates and a real parse confirms the key, which the LIKE
    alone cannot (``"task_id": 5`` is a substring of ``"task_id": 55``).
    """
    needle = f'"{key}": {json.dumps(value)}'
    rows = db.query(XPEvent).filter(XPEvent.event_type == event_type, XPEvent.metadata_json.like(f"%{needle}%")).all()
    for row in rows:
        try:
            meta = json.loads(row.metadata_json or "{}")
        except (TypeError, ValueError):
            continue
        if isinstance(meta, dict) and meta.get(key) == value:
            return True
    return False


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
    already_completed = _xp_event_recorded(db, "calendar_task_completed", "task_id", task.id) or _xp_event_recorded(
        db, "calendar_task_completed_no_time", "task_id", task.id
    )
    if not already_completed:
        process_event(db, event, {"task_id": task.id, "title": task.title, "date": str(task.date)})

    if task.date is None:
        return
    # Day fully planned bonus: no open tasks left for that date.
    open_left = (
        db.query(CalendarTask)
        .filter(CalendarTask.date == task.date, CalendarTask.done.is_(False), CalendarTask.id != task.id)
        .count()
    )
    if open_left == 0 and not _xp_event_recorded(db, "day_fully_planned", "date", str(task.date)):
        process_event(db, "day_fully_planned", {"date": str(task.date)})


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


def _apply_done_transition(db: Session, task: CalendarTask, was_done: bool) -> None:
    if not was_done and task.done:
        _award_task_xp(db, task)
        _adjust_goal_progress(db, task, 1)
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


class CalendarTaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    date: date_type | None = None
    start_time: time | None = None
    end_time: time | None = None
    priority: CalendarTaskPriority | None = None
    done: bool | None = None
    goal_id: int | None = None
    color: str | None = Field(default=None, max_length=20)
    # Write-back mirror (#1233): set by the frontend after creating the
    # Google event, so later edits/deletes can propagate to Google.
    google_event_id: str | None = Field(default=None, max_length=255)


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
    source: CalendarTaskSource
    google_event_id: str | None
    color: str | None
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
        source=task.source,
        google_event_id=task.google_event_id,
        color=task.color,
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
    return [_task_out(t) for t in query.all()]


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
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return _task_out(task)


@router.patch("/tasks/{task_id}", response_model=CalendarTaskOut)
def update_task(task_id: int, body: CalendarTaskUpdate, db: Session = Depends(get_db)):
    task = _get_or_404(db, task_id)
    data = body.model_dump(exclude_unset=True)
    was_done = task.done
    if "done" in data:
        task.done = data.pop("done")
        task.done_at = datetime.now(UTC) if task.done else None
    if "goal_id" in data:
        goal_id = data.pop("goal_id")
        if goal_id is not None and not db.get(Goal, goal_id):
            raise HTTPException(status_code=404, detail="Goal not found")
        task.goal_id = goal_id
    for field in ("title", "date", "start_time", "end_time", "priority", "color", "google_event_id"):
        if field in data:
            setattr(task, field, data[field])
    _validate_times(cast("time | None", task.start_time), cast("time | None", task.end_time))
    db.commit()
    db.refresh(task)
    _apply_done_transition(db, task, was_done)
    return _task_out(task)


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = _get_or_404(db, task_id)
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
    return _task_out(task)
