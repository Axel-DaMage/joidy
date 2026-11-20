"""CRUD for internal joidy calendar tasks (#1230)."""

from datetime import UTC, datetime, time
from datetime import date as date_type
from typing import cast

from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from models.calendar_task import CalendarTask, CalendarTaskPriority, CalendarTaskSource
from models.goal import Goal
from pydantic import BaseModel, Field
from services.gamification_engine import process_event
from sqlalchemy.orm import Session

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _award_task_xp(db: Session, task: CalendarTask) -> None:
    """Award XP for completing a planned task (#1235).

    Anti-double-count: a task linked to a goal only awards XP through one
    channel. Since completing the goal already fires `goal_completed` (+50),
    a linked task awards nothing — the greater XP wins.
    `day_fully_planned` fires when the last open task of the day is completed.
    """
    if task.goal_id is not None:
        return
    event = "calendar_task_completed" if task.start_time else "calendar_task_completed_no_time"
    process_event(db, event, {"task_id": task.id, "title": task.title, "date": str(task.date)})

    # Day fully planned bonus: no open tasks left for that date.
    open_left = (
        db.query(CalendarTask)
        .filter(CalendarTask.date == task.date, CalendarTask.done.is_(False), CalendarTask.id != task.id)
        .count()
    )
    if open_left == 0:
        process_event(db, "day_fully_planned", {"date": str(task.date)})


class CalendarTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    date: date_type
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
    date: date_type
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
    db: Session = Depends(get_db),
):
    query = db.query(CalendarTask)
    if date:
        query = query.filter(CalendarTask.date == _parse_date(date))
    if start:
        query = query.filter(CalendarTask.date >= _parse_date(start))
    if end:
        query = query.filter(CalendarTask.date <= _parse_date(end))
    query = query.order_by(CalendarTask.date.asc(), CalendarTask.start_time.asc().nullslast(), CalendarTask.id.asc())
    return [_task_out(t) for t in query.all()]


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
    if not was_done and task.done:
        _award_task_xp(db, task)
        db.commit()
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
    if not was_done and task.done:
        _award_task_xp(db, task)
        db.commit()
    return _task_out(task)
