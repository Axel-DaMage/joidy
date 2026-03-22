from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.goal import Goal
from models.note import NoteTag
from services.gamification_engine import process_event

router = APIRouter(prefix="/goals", tags=["goals"])


class GoalCreate(BaseModel):
    title: str
    description: str = ""
    target_notes: int = 5
    tag_id: Optional[int] = None


class GoalUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    target_notes: Optional[int] = None
    tag_id: Optional[int] = None


def _goal_progress(goal: Goal, db: Session) -> int:
    if goal.tag_id:
        return db.query(NoteTag).filter(NoteTag.tag_id == goal.tag_id).count()
    return 0


def _serialize_goal(goal: Goal, db: Session) -> dict:
    progress = _goal_progress(goal, db)
    return {
        "id": goal.id,
        "title": goal.title,
        "description": goal.description,
        "target_notes": goal.target_notes,
        "tag_id": goal.tag_id,
        "progress": progress,
        "progress_pct": min(100, int(progress / max(goal.target_notes, 1) * 100)),
        "is_completed": goal.is_completed,
        "completed_at": goal.completed_at.isoformat() if goal.completed_at else None,
        "created_at": goal.created_at.isoformat(),
    }


@router.get("/")
def list_goals(db: Session = Depends(get_db)):
    goals = db.query(Goal).order_by(Goal.is_completed, Goal.created_at.desc()).all()
    return [_serialize_goal(g, db) for g in goals]


@router.post("/", status_code=201)
def create_goal(data: GoalCreate, db: Session = Depends(get_db)):
    goal = Goal(**data.model_dump())
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return _serialize_goal(goal, db)


@router.put("/{goal_id}")
def update_goal(goal_id: int, data: GoalUpdate, db: Session = Depends(get_db)):
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(goal, field, value)
    db.commit()
    return _serialize_goal(goal, db)


@router.post("/{goal_id}/complete")
def complete_goal(goal_id: int, db: Session = Depends(get_db)):
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    goal.is_completed = True
    goal.completed_at = datetime.utcnow()
    gami = process_event(db, "goal_completed", {"goal_id": goal_id, "title": goal.title})
    db.commit()
    return {"goal": _serialize_goal(goal, db), "gamification": vars(gami)}


@router.delete("/{goal_id}", status_code=204)
def delete_goal(goal_id: int, db: Session = Depends(get_db)):
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    db.delete(goal)
    db.commit()
