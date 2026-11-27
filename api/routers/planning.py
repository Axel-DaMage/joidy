from datetime import UTC, date, datetime

from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from models.calendar_task import (
    CalendarTask,
    CalendarTaskPriority,
    CalendarTaskRecurrence,
)
from models.goal import Goal
from models.planning import PlanningAssignment
from pydantic import BaseModel
from services import task_google_sync
from services.response_cache import invalidate_cache_groups, register_cache_clearer, ttl_cache
from sqlalchemy.orm import Session

router = APIRouter(prefix="/planning", tags=["planning"])


class AssignmentsIn(BaseModel):
    date: str
    goal_ids: list[int]
    # Planning assignments mirror into calendar_tasks by default so the real
    # calendar reflects them (#goal-planning-calendar). Pass false to opt out.
    create_calendar_task: bool = True


class AssignmentsOut(BaseModel):
    date: str
    goal_ids: list[int]


@ttl_cache(ignore_params={"db"})
def _cached_assignments(date: str | None = None, db: Session = Depends(get_db)):
    if not date:
        raise HTTPException(status_code=400, detail="date is required")
    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    rows = db.query(PlanningAssignment).filter(PlanningAssignment.date == date_obj).all()
    return {"date": date, "goal_ids": [r.goal_id for r in rows]}


register_cache_clearer(_cached_assignments.cache_clear, groups={"planning"})


def _mirror_new_assignments_to_tasks(db: Session, date_obj: date, new_goal_ids: list[int]) -> list[CalendarTask]:
    """Create a calendar_task per newly assigned goal (#1234).

    Skips goals that already have a task on that date so re-saving the same
    assignments does not duplicate tasks. Returns the created tasks so the
    caller can publish them to Google Calendar.
    """
    if not new_goal_ids:
        return []
    goals_by_id = {g.id: g for g in db.query(Goal).filter(Goal.id.in_(new_goal_ids)).all()}
    already = {
        t.goal_id
        for t in db.query(CalendarTask)
        .filter(CalendarTask.date == date_obj, CalendarTask.goal_id.in_(new_goal_ids))
        .all()
    }
    created: list[CalendarTask] = []
    for gid in dict.fromkeys(new_goal_ids):
        goal = goals_by_id.get(gid)
        if goal is None or gid in already:
            continue
        task = CalendarTask(title=goal.title, date=date_obj, goal_id=goal.id)
        db.add(task)
        created.append(task)
    return created


def _is_pristine_mirror(task: CalendarTask, goal_title: str) -> bool:
    """True when ``task`` still looks exactly like an auto-created mirror.

    Any user customization (time, priority, recurrence, reminder, color,
    completion) detaches it from the mirror so unassigning the goal never
    destroys work the user did in the calendar. ``google_event_id`` is NOT
    checked: scheduled tasks auto-publish to Google, so every mirror owns a
    remote event by default — unpublish handles its cleanup on removal.
    """
    return (
        task.title == goal_title
        and task.start_time is None
        and task.end_time is None
        and task.priority == CalendarTaskPriority.MEDIUM
        and task.recurrence == CalendarTaskRecurrence.NONE
        and task.reminder_minutes is None
        and task.color is None
        and not task.done
    )


def _remove_pristine_mirrors(db: Session, date_obj: date, removed_goal_ids: list[int]) -> None:
    """Delete untouched mirror tasks for goals unassigned from ``date_obj``.

    Keeps the planning ↔ calendar link coherent: unassigning a goal removes
    the calendar entry the mirror created, unless the user already turned it
    into a real task (customized fields) — those survive as standalone tasks.
    """
    if not removed_goal_ids:
        return
    goals_by_id = {g.id: g for g in db.query(Goal).filter(Goal.id.in_(removed_goal_ids)).all()}
    tasks = (
        db.query(CalendarTask).filter(CalendarTask.date == date_obj, CalendarTask.goal_id.in_(removed_goal_ids)).all()
    )
    for task in tasks:
        goal = goals_by_id.get(task.goal_id) if task.goal_id is not None else None
        if goal is not None and _is_pristine_mirror(task, goal.title):
            # Auto-published mirrors own a Google event — remove it too so
            # unassigning the goal does not orphan an all-day event upstream.
            task_google_sync.unpublish_task(db, task)
            db.delete(task)


@router.get("/assignments")
def get_assignments(date: str | None = None, db: Session = Depends(get_db)):
    return _cached_assignments(date=date, db=db)


@router.post("/assignments")
def set_assignments(data: AssignmentsIn, db: Session = Depends(get_db)):
    try:
        date_obj = datetime.strptime(data.date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    previous_ids = {r.goal_id for r in db.query(PlanningAssignment).filter(PlanningAssignment.date == date_obj).all()}
    new_ids = set(data.goal_ids)
    removed_ids = [gid for gid in previous_ids if gid not in new_ids]
    # Replace assignments for the given date
    # Delete existing
    db.query(PlanningAssignment).filter(PlanningAssignment.date == date_obj).delete()
    # Insert new
    for gid in data.goal_ids:
        pa = PlanningAssignment(date=date_obj, goal_id=gid, created_at=datetime.now(UTC))
        db.add(pa)
    mirrored: list[CalendarTask] = []
    if data.create_calendar_task:
        mirrored = _mirror_new_assignments_to_tasks(
            db, date_obj, [gid for gid in data.goal_ids if gid not in previous_ids]
        ) or []
    _remove_pristine_mirrors(db, date_obj, removed_ids)
    db.commit()
    invalidate_cache_groups("planning")
    # Scheduled tasks mirror to Google Calendar as all-day events — publish
    # each new mirror (best-effort, never breaks the assignment).
    for task in mirrored:
        task_google_sync.sync_task(db, task)
    return {"date": data.date, "goal_ids": data.goal_ids}
