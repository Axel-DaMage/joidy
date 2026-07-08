import re
from datetime import datetime

from database import get_db
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from models.goal import (
    Goal,
    GoalFailConfig,
    GoalMeasurement,
    GoalState,
    GoalTemporality,
)
from pydantic import BaseModel, field_validator
from services.sanitizer import sanitize_title, sanitize_content, sanitize_color, sanitize_emoji
from services.gamification_engine import process_event
from services.goal_service import (
    evaluate_active_goals,
    get_goal_progress,
    get_goal_streak,
    resolve_pending_removal,
)
from services.joidy_vault_writer import (
    _write_goal_file,
    delete_goal_file,
    get_objectives_dir,
    read_goal_file,
    update_goal_file,
)
from sqlalchemy.orm import Session

router = APIRouter(prefix="/goals", tags=["goals"])




class GoalCreate(BaseModel):
    """Schema for creating a new goal."""
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
    note_id: int | None = None
    tag_id: int | None = None
    parent_id: int | None = None
    max_assignment_days: int | None = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        return sanitize_title(v)

    @field_validator("target_value")
    @classmethod
    def target_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Target value must be positive")
        return v

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        return sanitize_color(v)

    @field_validator("fail_emoji")
    @classmethod
    def validate_emoji(cls, v: str) -> str:
        return sanitize_emoji(v)

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        return sanitize_content(v)


class GoalUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    temporality: GoalTemporality | None = None
    measurement_type: GoalMeasurement | None = None
    target_value: float | None = None
    current_value: float | None = None
    state: GoalState | None = None
    fail_config: GoalFailConfig | None = None
    fail_emoji: str | None = None
    color: str | None = None
    theme: str | None = None
    note_id: int | None = None
    tag_id: int | None = None
    max_assignment_days: int | None = None
    content: str | None = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return sanitize_title(v)

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return sanitize_content(v)

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return sanitize_color(v)

    @field_validator("fail_emoji")
    @classmethod
    def validate_emoji(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return sanitize_emoji(v)

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return sanitize_content(v)



class GoalContent(BaseModel):
    title: str
    content: str
    temporality: GoalTemporality = GoalTemporality.DAILY
    measurement_type: GoalMeasurement = GoalMeasurement.COUNT
    target_value: float = 1.0
    state: GoalState = GoalState.ACTIVE
    fail_config: GoalFailConfig = GoalFailConfig.STATIC
    fail_emoji: str = "🔴"
    color: str = "#c8a96e"
    theme: str = "solid"
    note_id: int | None = None
    tag_id: int | None = None
    parent_id: int | None = None
    max_assignment_days: int | None = None
    description: str = ""




def _serialize_goal(goal: Goal, db: Session) -> dict:
    progress = get_goal_progress(goal, db)
    return {
        "id": goal.id,
        "title": goal.title,
        "description": goal.description,
        "source_path": goal.source_path,
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
        "max_assignment_days": goal.max_assignment_days,
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

    obj_dir = get_objectives_dir()
    if obj_dir:
        _write_goal_file(db, goal, obj_dir)

    return _serialize_goal(goal, db)


@router.put("/{goal_id}")
def update_goal(goal_id: int, data: GoalUpdate, db: Session = Depends(get_db)):
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    update_data = data.model_dump(exclude_none=True)
    content = update_data.pop("content", None)

    for field, value in update_data.items():
        setattr(goal, field, value)

    db.commit()

    if content is not None:
        metadata = {
            "temporality": goal.temporality,
            "measurement_type": goal.measurement_type,
            "target_value": goal.target_value,
            "current_value": goal.current_value,
            "state": goal.state,
            "fail_config": goal.fail_config,
            "fail_emoji": goal.fail_emoji,
            "color": goal.color,
            "theme": goal.theme,
            "note_id": goal.note_id,
            "tag_id": goal.tag_id,
            "parent_id": goal.parent_id,
            "max_assignment_days": goal.max_assignment_days,
            "is_completed": goal.is_completed,
            "completed_at": goal.completed_at.isoformat() if goal.completed_at else None,
        }
        update_goal_file(goal_id, goal.title, content, metadata)

    return _serialize_goal(goal, db)



@router.get("/{goal_id}")
def get_goal(goal_id: int, db: Session = Depends(get_db)):
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return _serialize_goal(goal, db)


@router.get("/{goal_id}/content")
def get_goal_content(goal_id: int, db: Session = Depends(get_db)):
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    file_data = read_goal_file(goal_id)
    if file_data:
        return file_data

    return {
        "title": goal.title,
        "content": goal.description or "",
        "temporality": goal.temporality,
        "measurement_type": goal.measurement_type,
        "target_value": goal.target_value,
        "state": goal.state,
        "fail_config": goal.fail_config,
        "fail_emoji": goal.fail_emoji,
        "color": goal.color,
        "theme": goal.theme,
        "note_id": goal.note_id,
        "tag_id": goal.tag_id,
        "max_assignment_days": goal.max_assignment_days,
    }


@router.post("/{goal_id}/content")
def save_goal_content(goal_id: int, data: GoalContent, db: Session = Depends(get_db)):
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    goal.title = data.title
    goal.description = data.content
    goal.temporality = data.temporality
    goal.measurement_type = data.measurement_type
    goal.target_value = data.target_value
    goal.state = data.state
    goal.fail_config = data.fail_config
    goal.fail_emoji = data.fail_emoji
    goal.color = data.color
    goal.theme = data.theme
    goal.note_id = data.note_id
    goal.tag_id = data.tag_id
    goal.parent_id = data.parent_id
    goal.max_assignment_days = data.max_assignment_days

    db.commit()

    obj_dir = get_objectives_dir()
    if obj_dir:
        metadata = {
            "temporality": goal.temporality,
            "measurement_type": goal.measurement_type,
            "target_value": goal.target_value,
            "current_value": goal.current_value,
            "state": goal.state,
            "fail_config": goal.fail_config,
            "fail_emoji": goal.fail_emoji,
            "color": goal.color,
            "theme": goal.theme,
            "note_id": goal.note_id,
            "tag_id": goal.tag_id,
            "parent_id": goal.parent_id,
            "max_assignment_days": goal.max_assignment_days,
            "is_completed": goal.is_completed,
            "completed_at": goal.completed_at.isoformat() if goal.completed_at else None,
        }
        update_goal_file(goal_id, data.title, data.content, metadata)

    return _serialize_goal(goal, db)


@router.post("/{goal_id}/complete")
def complete_goal(
    goal_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
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

    delete_goal_file(goal_id)
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
