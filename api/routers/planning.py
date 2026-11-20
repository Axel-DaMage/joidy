from datetime import UTC, date, datetime

from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from models.calendar_task import CalendarTask
from models.goal import Goal
from models.planning import PlanningAssignment
from pydantic import BaseModel
from services.response_cache import clear_api_caches, register_cache_clearer, ttl_cache
from sqlalchemy.orm import Session

router = APIRouter(prefix="/planning", tags=["planning"])


class AssignmentsIn(BaseModel):
    date: str
    goal_ids: list[int]
    # When true, newly assigned goals also get a calendar_task on that date
    # (title = goal title, goal_id linked, source=JOIDY; #1234).
    create_calendar_task: bool = False


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


register_cache_clearer(_cached_assignments.cache_clear)


def _mirror_new_assignments_to_tasks(db: Session, date_obj: date, new_goal_ids: list[int]) -> None:
    """Create a calendar_task per newly assigned goal (#1234).

    Skips goals that already have a task on that date so re-saving the same
    assignments does not duplicate tasks.
    """
    if not new_goal_ids:
        return
    goals_by_id = {g.id: g for g in db.query(Goal).filter(Goal.id.in_(new_goal_ids)).all()}
    already = {
        t.goal_id
        for t in db.query(CalendarTask)
        .filter(CalendarTask.date == date_obj, CalendarTask.goal_id.in_(new_goal_ids))
        .all()
    }
    for gid in new_goal_ids:
        goal = goals_by_id.get(gid)
        if goal is None or gid in already:
            continue
        db.add(CalendarTask(title=goal.title, date=date_obj, goal_id=goal.id))


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
    # Replace assignments for the given date
    # Delete existing
    db.query(PlanningAssignment).filter(PlanningAssignment.date == date_obj).delete()
    # Insert new
    for gid in data.goal_ids:
        pa = PlanningAssignment(date=date_obj, goal_id=gid, created_at=datetime.now(UTC))
        db.add(pa)
    if data.create_calendar_task:
        _mirror_new_assignments_to_tasks(db, date_obj, [gid for gid in data.goal_ids if gid not in previous_ids])
    db.commit()
    clear_api_caches()
    return {"date": data.date, "goal_ids": data.goal_ids}
