from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.goal import Goal, GoalTemporality, GoalMeasurement, GoalState, GoalFailConfig
from models.note import NoteTag
from services.gamification_engine import process_event
from services.goal_service import get_goal_progress, evaluate_active_goals, get_goal_streak, resolve_pending_removal

router = APIRouter(prefix="/goals", tags=["goals"])


class GoalCreate(BaseModel):
    title: str
    description: str = ""
    temporality: GoalTemporality = GoalTemporality.DAILY
    measurement_type: GoalMeasurement = GoalMeasurement.COUNT
    target_value: float = 1.0
    state: GoalState = GoalState.ACTIVE
    fail_config: GoalFailConfig = GoalFailConfig.STATIC
    fail_emoji: str = "🔴"
    color: str = "#c8a96e"
    theme: str = "solid"
    note_id: Optional[int] = None
    tag_id: Optional[int] = None
    parent_id: Optional[int] = None


class GoalUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    temporality: Optional[GoalTemporality] = None
    measurement_type: Optional[GoalMeasurement] = None
    target_value: Optional[float] = None
    current_value: Optional[float] = None
    state: Optional[GoalState] = None
    fail_config: Optional[GoalFailConfig] = None
    fail_emoji: Optional[str] = None
    color: Optional[str] = None
    theme: Optional[str] = None
    note_id: Optional[int] = None
    tag_id: Optional[int] = None




def _serialize_goal(goal: Goal, db: Session) -> dict:
    progress = get_goal_progress(goal, db)
    return {
        "id": goal.id,
        "title": goal.title,
        "description": goal.description,
        "temporality": goal.temporality,
        "measurement_type": goal.measurement_type,
        "target_value": goal.target_value,
        "current_value": progress,
        "state": goal.state,
        "fail_config": goal.fail_config,
        "fail_emoji": goal.fail_emoji,
        "color": goal.color,
        "theme": goal.theme,
        "note_id": goal.note_id,
        "tag_id": goal.tag_id,
        "parent_id": goal.parent_id,
        "progress_pct": min(100, int(progress / max(goal.target_value, 1) * 100)),
        "pending_removal": goal.pending_removal,
        "is_completed": goal.is_completed,
        "completed_at": goal.completed_at.isoformat() if goal.completed_at else None,
        "created_at": goal.created_at.isoformat(),
        "updated_at": goal.updated_at.isoformat(),
    }


@router.get("/")
def list_goals(db: Session = Depends(get_db)):
    evaluate_active_goals(db)
    goals = db.query(Goal).order_by(Goal.is_completed, Goal.created_at.desc()).all()
    return [_serialize_goal(g, db) for g in goals]


@router.get("/streak")
def goal_streak(db: Session = Depends(get_db)):
    return get_goal_streak(db)


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
    goal.state = GoalState.COMPLETED
    goal.completed_at = datetime.utcnow()
    goal.current_value = get_goal_progress(goal, db)
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


class ResolveRemoval(BaseModel):
    action: str  # 'delete' | 'manual' | 'cancel'


@router.post("/{goal_id}/resolve-removal")
def resolve_removal(goal_id: int, data: ResolveRemoval, db: Session = Depends(get_db)):
    goal = resolve_pending_removal(db, goal_id, data.action)
    db.commit()
    if goal is None and data.action == "delete":
        return {"status": "deleted"}
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return _serialize_goal(goal, db)
