from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.planning import PlanningAssignment
from services.response_cache import clear_api_caches, register_cache_clearer, ttl_cache

router = APIRouter(prefix="/planning", tags=["planning"])


class AssignmentsIn(BaseModel):
    date: str
    goal_ids: List[int]


class AssignmentsOut(BaseModel):
    date: str
    goal_ids: List[int]


@ttl_cache(ignore_params={"db"})
def _cached_assignments(date: Optional[str] = None, db: Session = Depends(get_db)):
    if not date:
        raise HTTPException(status_code=400, detail="date is required")
    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    rows = db.query(PlanningAssignment).filter(PlanningAssignment.date == date_obj).all()
    return {"date": date, "goal_ids": [r.goal_id for r in rows]}


register_cache_clearer(_cached_assignments.cache_clear)  # type: ignore[attr-defined]


@router.get("/assignments")
def get_assignments(date: Optional[str] = None, db: Session = Depends(get_db)):
    return _cached_assignments(date=date, db=db)


@router.post("/assignments")
def set_assignments(data: AssignmentsIn, db: Session = Depends(get_db)):
    try:
        date_obj = datetime.strptime(data.date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # Replace assignments for the given date
    # Delete existing
    db.query(PlanningAssignment).filter(PlanningAssignment.date == date_obj).delete()
    # Insert new
    for gid in data.goal_ids:
        pa = PlanningAssignment(date=date_obj, goal_id=gid, created_at=datetime.utcnow())
        db.add(pa)
    db.commit()
    clear_api_caches()
    return {"date": data.date, "goal_ids": data.goal_ids}
