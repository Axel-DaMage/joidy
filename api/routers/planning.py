from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.planning import PlanningAssignment

router = APIRouter(prefix="/planning", tags=["planning"])


class AssignmentsIn(BaseModel):
    date: str
    goal_ids: List[int]


class AssignmentsOut(BaseModel):
    date: str
    goal_ids: List[int]


@router.get("/assignments")
def get_assignments(date: Optional[str] = None, db: Session = Depends(get_db)):
    if not date:
        raise HTTPException(status_code=400, detail="date is required")
    rows = db.query(PlanningAssignment).filter(PlanningAssignment.date == date).all()
    return {"date": date, "goal_ids": [r.goal_id for r in rows]}


@router.post("/assignments")
def set_assignments(data: AssignmentsIn, db: Session = Depends(get_db)):
    # Replace assignments for the given date
    # Delete existing
    db.query(PlanningAssignment).filter(PlanningAssignment.date == data.date).delete()
    # Insert new
    for gid in data.goal_ids:
        pa = PlanningAssignment(date=data.date, goal_id=gid, created_at=datetime.utcnow())
        db.add(pa)
    db.commit()
    return {"date": data.date, "goal_ids": data.goal_ids}
