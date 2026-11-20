from datetime import UTC, datetime

from database import get_db
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from models.goal import (
    Goal,
    GoalContext,
    GoalFailConfig,
    GoalMeasurement,
    GoalState,
    GoalTemporality,
)
from models.note import Note
from pydantic import BaseModel, field_validator
from services.gamification_engine import process_event
from services.goal_service import (
    evaluate_active_goals,
    get_bulk_goal_progress,
    get_goal_progress,
    get_goal_streak,
    resolve_pending_removal,
    validate_goal_parent,
)
from services.joidy_vault_writer import (
    _write_goal_file,
    delete_goal_file,
    get_objectives_dir,
    read_goal_file,
    update_goal_file,
)
from services.note_service import write_to_vault
from services.sanitizer import sanitize_color, sanitize_content, sanitize_emoji, sanitize_theme, sanitize_title
from services.sync_service import update_local_mtime
from services.timezone_utils import get_local_now
from sqlalchemy.orm import Session

router = APIRouter(prefix="/goals", tags=["goals"])


GOAL_PRIORITY_MAX = 99


def _validate_priority_range(v: int) -> int:
    if not 0 <= v <= GOAL_PRIORITY_MAX:
        raise ValueError(f"Priority must be between 0 and {GOAL_PRIORITY_MAX}")
    return v


def _reject_newlines(v: str, field: str) -> str:
    """Reject CR/LF in single-line scalars written verbatim into vault
    ``.md`` files — a newline injects extra frontmatter keys or body
    lines (``theme="x\\nstate: COMPLETED"``, ``# {title}`` headings) (#1319)."""
    if "\n" in v or "\r" in v:
        raise ValueError(f"{field} must be a single line")
    return v


# Terminal goal states carry side effects (XP award, ``completed_at``,
# snowball redistribution) and must be reached only through the dedicated
# /complete and /fail endpoints — never via plain create/update payloads,
# which would fabricate phantom completions (#1319).
_GOAL_TERMINAL_STATES = frozenset({GoalState.COMPLETED, GoalState.FAILED})


def _reject_terminal_state(v: GoalState) -> GoalState:
    if v in _GOAL_TERMINAL_STATES:
        raise ValueError(
            "Goal state can only become COMPLETED or FAILED via POST /goals/{id}/complete or POST /goals/{id}/fail"
        )
    return v


def _validate_note_exists(db: Session, note_id: int) -> None:
    """Reject linking a goal to a note that does not exist — the save path
    would otherwise overwrite an arbitrary/absent note body or blow up with
    a FK IntegrityError (500) (#1319)."""
    if db.query(Note).filter(Note.id == note_id).first() is None:
        raise HTTPException(status_code=404, detail="Note not found")


def _validate_tag_exists(db: Session, tag_id: int) -> None:
    """Same existence guarantee as ``_validate_note_exists`` for the
    ``tag_id`` FK — avoids raw IntegrityError 500s on bogus ids (#1319)."""
    from models.note import Tag

    if db.query(Tag).filter(Tag.id == tag_id).first() is None:
        raise HTTPException(status_code=404, detail="Tag not found")


class GoalCreate(BaseModel):
    """Schema for creating a new goal.

    ``priority`` uses a higher-wins scale: 0 = no explicit priority, higher
    numbers float to the top of every goal listing (sorted DESC, #1097).
    """

    title: str
    description: str = ""
    temporality: GoalTemporality = GoalTemporality.ONEOFF
    context: GoalContext = GoalContext.ANY
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
    priority: int = 0

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        return _reject_newlines(sanitize_title(v), "Title")

    @field_validator("target_value")
    @classmethod
    def target_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Target value must be positive")
        return v

    @field_validator("state")
    @classmethod
    def state_not_terminal(cls, v: GoalState) -> GoalState:
        return _reject_terminal_state(v)

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        return sanitize_color(v)

    @field_validator("theme")
    @classmethod
    def validate_theme(cls, v: str) -> str:
        return sanitize_theme(v)

    @field_validator("fail_emoji")
    @classmethod
    def validate_emoji(cls, v: str) -> str:
        return sanitize_emoji(v)

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        return sanitize_content(v)

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: int) -> int:
        return _validate_priority_range(v)


class GoalUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    temporality: GoalTemporality | None = None
    context: GoalContext | None = None
    measurement_type: GoalMeasurement | None = None
    target_value: float | None = None
    # ``current_value`` is computed server-side (get_goal_progress) and is not
    # client-settable; extra fields are ignored by Pydantic, so a stray
    # ``{"current_value": 999}`` is silently dropped rather than stored (#1319).
    state: GoalState | None = None
    fail_config: GoalFailConfig | None = None
    fail_emoji: str | None = None
    color: str | None = None
    theme: str | None = None
    note_id: int | None = None
    tag_id: int | None = None
    max_assignment_days: int | None = None
    content: str | None = None
    priority: int | None = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _reject_newlines(sanitize_title(v), "Title")

    @field_validator("target_value")
    @classmethod
    def target_positive(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if v <= 0:
            raise ValueError("Target value must be positive")
        return v

    @field_validator("state")
    @classmethod
    def state_not_terminal(cls, v: GoalState | None) -> GoalState | None:
        # Pause/cancel/reactivate/un-complete via PUT stays allowed; only the
        # side-effectful terminal states are forced through /complete|/fail.
        if v is None:
            return v
        return _reject_terminal_state(v)

    @field_validator("theme")
    @classmethod
    def validate_theme(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return sanitize_theme(v)

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

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: int | None) -> int | None:
        if v is None:
            return v
        return _validate_priority_range(v)


class GoalContent(BaseModel):
    """Payload for POST /goals/{id}/content — mirrors GoalCreate's
    sanitization so editor saves cannot inject XSS into stored titles or
    extra keys into vault frontmatter (#1319).

    ``state`` is accepted for payload compatibility with GET /content's
    response shape but is NEVER applied server-side — state transitions
    must go through PUT /goals/{id} (non-terminal) or /complete|/fail.
    """

    title: str
    content: str
    temporality: GoalTemporality = GoalTemporality.ONEOFF
    context: GoalContext = GoalContext.ANY
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

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        return _reject_newlines(sanitize_title(v), "Title")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        return sanitize_content(v)

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        return sanitize_content(v)

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

    @field_validator("theme")
    @classmethod
    def validate_theme(cls, v: str) -> str:
        return sanitize_theme(v)

    @field_validator("fail_emoji")
    @classmethod
    def validate_emoji(cls, v: str) -> str:
        return sanitize_emoji(v)


def _serialize_goal(goal: Goal, db: Session, precalculated_progress: float | None = None) -> dict:
    progress = precalculated_progress if precalculated_progress is not None else get_goal_progress(goal, db)
    return {
        "id": goal.id,
        "title": goal.title,
        "description": goal.description,
        "source_path": goal.source_path,
        "temporality": goal.temporality,
        "context": goal.context,
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
        "priority": goal.priority,
        "progress_pct": min(100, int(progress / max(goal.target_value, 1) * 100)),
        "pending_removal": goal.pending_removal,
        "is_completed": goal.is_completed,
        "completed_at": goal.completed_at.isoformat() if goal.completed_at else None,
        "created_at": goal.created_at.isoformat(),
        "updated_at": goal.updated_at.isoformat(),
    }


@router.get("/")
def list_goals(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    state: GoalState | None = Query(None),
    context: GoalContext | None = Query(None),
    db: Session = Depends(get_db),
):
    evaluate_active_goals(db)
    query = db.query(Goal)
    if state is not None:
        query = query.filter(Goal.state == state)
    if context is not None:
        query = query.filter(Goal.context == context)
    goals = (
        query.order_by(Goal.is_completed, Goal.priority.desc(), Goal.created_at.desc()).offset(skip).limit(limit).all()
    )
    progress_map = get_bulk_goal_progress(goals, db)
    return [_serialize_goal(g, db, precalculated_progress=progress_map.get(g.id)) for g in goals]


@router.get("/streak")
def goal_streak(db: Session = Depends(get_db)):
    return get_goal_streak(db)


@router.post("/", status_code=201)
def create_goal(data: GoalCreate, db: Session = Depends(get_db)):
    # New goal has no id yet, so only parent existence can be violated, but
    # validate anyway for consistency and to reject non-existent parents.
    validate_goal_parent(db, goal_id=None, parent_id=data.parent_id)

    # FK targets must exist before linking — otherwise the commit dies with
    # a raw IntegrityError (500) and, for note_id, a later save would
    # silently overwrite an arbitrary note's body (#1319).
    if data.note_id is not None:
        _validate_note_exists(db, data.note_id)
    if data.tag_id is not None:
        _validate_tag_exists(db, data.tag_id)

    note_id = data.note_id
    if note_id is None:
        from services.note_service import create_note as create_note_service

        note_title = f"{data.title}"
        note_content = (
            f"# Objetivo: {data.title}\n\nEscribe aquí tus estrategias, pasos y registros para este objetivo.\n"
        )
        note, _ = create_note_service(
            db,
            title=note_title,
            content=note_content,
            tags=[],
            source="joidy",
            source_path=None,
            sync_goals=False,
        )
        note_id = note.id

    goal_data = data.model_dump()
    goal_data["note_id"] = note_id
    goal = Goal(**goal_data)
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

    if "parent_id" in update_data:
        validate_goal_parent(db, goal_id=goal.id, parent_id=update_data["parent_id"])

    # Linked FKs must exist before the setattr loop — a bogus note_id would
    # otherwise 500 on commit and open the linked-note overwrite path (#1319).
    if "note_id" in update_data:
        _validate_note_exists(db, update_data["note_id"])
    if "tag_id" in update_data:
        _validate_tag_exists(db, update_data["tag_id"])

    for field, value in update_data.items():
        setattr(goal, field, value)

    db.commit()

    if content is not None:
        metadata = {
            "temporality": goal.temporality,
            "context": goal.context,
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

        # #1141 — mirror into the linked real note (same as /content save).
        if goal.note_id is not None:
            linked_note = db.query(Note).filter(Note.id == goal.note_id).first()
            if linked_note is not None:
                linked_note.content = sanitize_content(content)
                db.commit()
                write_to_vault(linked_note)
                update_local_mtime(db, linked_note.id)
                db.commit()

    return _serialize_goal(goal, db)


class GoalSortItem(BaseModel):
    id: int
    priority: int

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: int) -> int:
        return _validate_priority_range(v)


class GoalSortRequest(BaseModel):
    items: list[GoalSortItem]


@router.patch("/sort")
def sort_goals(data: GoalSortRequest, db: Session = Depends(get_db)):
    ids = [item.id for item in data.items]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=422, detail="Duplicate goal ids in sort payload")

    goals = db.query(Goal).filter(Goal.id.in_(ids)).all() if ids else []
    found_ids = {g.id for g in goals}
    missing = [gid for gid in ids if gid not in found_ids]
    if missing:
        raise HTTPException(status_code=404, detail=f"Goals not found: {missing}")

    priority_by_id = {item.id: item.priority for item in data.items}
    for goal in goals:
        goal.priority = priority_by_id[goal.id]
    db.commit()
    return {"updated": len(goals)}


# Execution queue time-of-day threshold: hour < 15 is MORNING, else NIGHT.
# Morning slots target low-friction tasks; night slots focus on deep work (#1198).
EXECUTION_QUEUE_MORNING_CUTOFF_HOUR = 15


@router.get("/execution-queue")
def get_execution_queue(
    context: str = Query("auto", pattern="^(auto|morning|night)$"),
    db: Session = Depends(get_db),
):
    """Execution mode queue (#1198).

    Resolves active, uncompleted goals ordered by priority DESC, created_at DESC.
    Includes tasks matching the resolved context plus ANY tasks.
    """
    evaluate_active_goals(db)
    now_local = get_local_now()

    if context == "auto":
        resolved_context = (
            GoalContext.MORNING if now_local.hour < EXECUTION_QUEUE_MORNING_CUTOFF_HOUR else GoalContext.NIGHT
        )
    elif context == "morning":
        resolved_context = GoalContext.MORNING
    else:
        resolved_context = GoalContext.NIGHT

    goals = (
        db.query(Goal)
        .filter(
            Goal.state == GoalState.ACTIVE,
            Goal.is_completed.is_(False),
            Goal.context.in_([resolved_context, GoalContext.ANY]),
        )
        .order_by(Goal.priority.desc(), Goal.created_at.desc())
        .limit(50)
        .all()
    )

    progress_map = get_bulk_goal_progress(goals, db)
    items = [_serialize_goal(g, db, precalculated_progress=progress_map.get(g.id)) for g in goals]

    return {
        "context": resolved_context.value,
        "generated_at": datetime.now(UTC).isoformat(),
        "items": items,
    }


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

    # #1141 — when the goal is linked to a real note, the note is the source
    # of truth for its content; the editor reads/writes the note, not the
    # auto-generated goal file.
    if goal.note_id is not None:
        linked_note = db.query(Note).filter(Note.id == goal.note_id).first()
        if linked_note is not None:
            return {
                "title": goal.title,
                "content": linked_note.content or "",
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

    # FK targets must exist before linking — a bogus note_id used to 500 on
    # commit and let clients aim the linked-note overwrite below at any
    # note they chose (#1319). ``None`` unlinks, which is allowed.
    if data.note_id is not None:
        _validate_note_exists(db, data.note_id)
    if data.tag_id is not None:
        _validate_tag_exists(db, data.tag_id)

    goal.title = data.title
    goal.description = data.content
    goal.temporality = data.temporality
    goal.measurement_type = data.measurement_type
    goal.target_value = data.target_value
    # #1319 — data.state is deliberately NOT applied: the editor echoes the
    # current state back in every save, and mass-assigning it let clients
    # fabricate COMPLETED goals bypassing /complete (XP, completed_at,
    # snowball). Transitions: PUT /goals/{id} or /complete|/fail.
    goal.fail_config = data.fail_config
    goal.fail_emoji = data.fail_emoji
    goal.color = data.color
    goal.theme = data.theme
    goal.note_id = data.note_id
    goal.tag_id = data.tag_id
    validate_goal_parent(db, goal_id=goal.id, parent_id=data.parent_id)
    goal.parent_id = data.parent_id
    goal.max_assignment_days = data.max_assignment_days

    # #1141 — if the goal is linked to a real note, the written content must
    # land in that note instead of only the goal note file. Update directly
    # (not via update_note) so sync_goals_from_note does not flag this goal
    # as pending_removal when the note content lacks goal markers.
    linked_note = None
    if goal.note_id is not None:
        linked_note = db.query(Note).filter(Note.id == goal.note_id).first()
        if linked_note is not None:
            linked_note.content = sanitize_content(data.content)

    db.commit()

    obj_dir = get_objectives_dir()
    if obj_dir:
        metadata = {
            "temporality": goal.temporality,
            "context": goal.context,
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

    if linked_note is not None:
        write_to_vault(linked_note)
        update_local_mtime(db, linked_note.id)
        db.commit()

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

    was_failed = goal.state == GoalState.FAILED
    old_current = goal.current_value

    goal.is_completed = True
    goal.state = GoalState.COMPLETED
    goal.completed_at = datetime.now(UTC)
    goal.current_value = get_goal_progress(goal, db)

    # Adjust descendant goals if this was a late completion of a failed goal
    child = None
    if was_failed:
        child = (
            db.query(Goal)
            .filter(Goal.title == goal.title, Goal.state == GoalState.ACTIVE, Goal.created_at > goal.created_at)
            .order_by(Goal.created_at.asc())
            .first()
        )
        if child and goal.fail_config == GoalFailConfig.SNOWBALL:
            shortfall = max(0.0, goal.target_value - old_current)
            child.target_value = max(goal.target_value, child.target_value - shortfall)
            db.add(child)

    gami = process_event(db, "goal_completed", {"goal_id": goal_id, "title": goal.title})
    db.commit()
    db.refresh(goal)
    if child:
        db.refresh(child)

    # Sync updates back to the vault
    obj_dir = get_objectives_dir()
    if obj_dir:
        _write_goal_file(db, goal, obj_dir)
        if child:
            _write_goal_file(db, child, obj_dir)

    return {"goal": _serialize_goal(goal, db), "gamification": vars(gami)}


@router.post("/{goal_id}/fail")
def fail_goal(
    goal_id: int,
    db: Session = Depends(get_db),
):
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    goal.state = GoalState.FAILED
    goal.current_value = get_goal_progress(goal, db)
    db.commit()
    db.refresh(goal)

    obj_dir = get_objectives_dir()
    if obj_dir:
        _write_goal_file(db, goal, obj_dir)

    return _serialize_goal(goal, db)


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
