import re
from datetime import datetime, timedelta

from models.goal import (
    Goal,
    GoalFailConfig,
    GoalMeasurement,
    GoalState,
    GoalTemporality,
)
from models.note import Note, NoteTag
from repositories import GoalRepository
from sqlalchemy.orm import Session


def _parse_temporality(text: str) -> GoalTemporality:
    if not text:
        return GoalTemporality.DAILY
    text = text.lower()
    if text in ["diario", "daily"]:
        return GoalTemporality.DAILY
    if text in ["semanal", "weekly"]:
        return GoalTemporality.WEEKLY
    if text in ["mensual", "monthly"]:
        return GoalTemporality.MONTHLY
    if text in ["anual", "annual"]:
        return GoalTemporality.ANNUAL
    return GoalTemporality.DAILY

def _parse_fail_config(text: str) -> GoalFailConfig:
    if not text:
        return GoalFailConfig.STATIC
    text = text.lower()
    if text in ["rollover", "traspaso"]:
        return GoalFailConfig.ROLLOVER
    if text in ["snowball", "acumulativo"]:
        return GoalFailConfig.SNOWBALL
    return GoalFailConfig.STATIC

def parse_goals_from_content(content: str) -> list[dict]:
    """
    Parses lines like: # Objetivo: [Meta] [Unidad] @Periodo %Modo_Falla
    Returns a list of dicts with extracted data.
    """
    goals = []
    # Regex explanation:
    # # Objetivo:\s+ matches the prefix
    # (.*?)\s* matches the title (Meta + Unidad) lazily
    # (?:@(\w+))? optionally matches @Periodo
    # (?:\s+%(\w+))? optionally matches %Modo_Falla
    pattern = r"#\s*Objetivo:\s*(.*?)(?:\s+@(\w+))?(?:\s+%(\w+))?(?=$|\n|\r)"
    matches = re.finditer(pattern, content, re.IGNORECASE)

    for match in matches:
        title = match.group(1).strip() if match.group(1) else "Unnamed Goal"
        period = match.group(2)
        fail_mode = match.group(3)

        # Simple heuristic to extract numbers from title for target_value
        # Example: "5 notas", target = 5. "10 pages", target = 10.
        target_value = 1.0
        measurement_type = GoalMeasurement.BOOLEAN

        num_match = re.search(r'\b(\d+(?:\.\d+)?)\b', title)
        if num_match:
            target_value = float(num_match.group(1))
            measurement_type = GoalMeasurement.COUNT

        goals.append({
            "title": title,
            "temporality": _parse_temporality(period),
            "fail_config": _parse_fail_config(fail_mode),
            "target_value": target_value,
            "measurement_type": measurement_type,
            "state": GoalState.ACTIVE
        })
    return goals

def sync_goals_from_note(db: Session, note_id: int, content: str):
    """
    Syncs the parsed goals into the database for a specific note.
    - Creates new ones if not found.
    - Deactivates or drops old ones? For safety, we just add missing ones.
    (Bidirectional implies keeping them in sync, for now we will recreate or update based on title)
    """
    parsed_goals = parse_goals_from_content(content)

    # Get existing goals linked to this note
    existing_goals = GoalRepository(db).get_by_note(note_id)
    existing_by_title = {g.title: g for g in existing_goals}

    # Update or Create
    processed_titles = set()
    for pdata in parsed_goals:
        title = pdata["title"]
        processed_titles.add(title)

        if title in existing_by_title:
            g = existing_by_title[title]
            g.temporality = pdata["temporality"]
            g.fail_config = pdata["fail_config"]
            # Only update target if not already completed? We can overwrite.
            if g.state == GoalState.ACTIVE:
                g.target_value = pdata["target_value"]
                g.measurement_type = pdata["measurement_type"]
        else:
            new_goal = Goal(
                title=title,
                temporality=pdata["temporality"],
                fail_config=pdata["fail_config"],
                target_value=pdata["target_value"],
                measurement_type=pdata["measurement_type"],
                state=GoalState.ACTIVE,
                note_id=note_id
            )
            GoalRepository(db).add(new_goal)

    # Flag goals that were removed from the note content as pending_removal
    # instead of silently cancelling — the user decides via the Modal de Consistencia
    for g in existing_goals:
        if g.title not in processed_titles and g.state in (GoalState.ACTIVE, GoalState.PAUSED):
            g.pending_removal = True

    db.flush()


def resolve_pending_removal(db: Session, goal_id: int, action: str) -> Goal | None:
    """
    Resolve a pending_removal goal.
    action: 'delete' — remove the goal entirely
            'manual' — keep the goal but unlink it from the note (convert to manual tracking)
            'cancel' — cancel the goal (archive without penalty)
    """
    goal = GoalRepository(db).get(goal_id)
    if not goal:
        return None

    goal.pending_removal = False

    if action == "delete":
        GoalRepository(db).delete(goal)
        db.flush()
        return None
    elif action == "cancel":
        goal.state = GoalState.CANCELLED
    elif action == "manual":
        goal.note_id = None  # Unlink from note, keep as manual goal

    db.flush()
    return goal


def get_goal_progress(goal: Goal, db: Session) -> float:
    if goal.tag_id and goal.measurement_type == GoalMeasurement.COUNT:
        query = db.query(NoteTag).join(NoteTag.note).filter(NoteTag.tag_id == goal.tag_id)
        # Filter notes based on the goal's created_at (representing the start of the period)
        query = query.filter(Note.created_at >= goal.created_at)
        return float(query.count())
    return goal.current_value


def get_bulk_goal_progress(goals: list[Goal], db: Session) -> dict[int, float]:
    """Bulk retrieve goal progress to prevent N+1 queries."""
    result = {}
    count_goals = [g for g in goals if g.tag_id and g.measurement_type == GoalMeasurement.COUNT]
    
    if count_goals:
        goal_ids = [g.id for g in count_goals]
        from sqlalchemy import func
        from models.note import Note, NoteTag
        
        stmt = (
            db.query(Goal.id, func.count(Note.id))
            .outerjoin(NoteTag, NoteTag.tag_id == Goal.tag_id)
            .outerjoin(Note, (Note.id == NoteTag.note_id) & (Note.created_at >= Goal.created_at))
            .filter(Goal.id.in_(goal_ids))
            .group_by(Goal.id)
        )
        for goal_id, count in stmt.all():
            result[goal_id] = float(count)
            
    for g in goals:
        if g.id not in result:
            result[g.id] = g.current_value
            
    return result


def evaluate_active_goals(db: Session):
    now = datetime.utcnow()
    active_goals = GoalRepository(db).get_active()

    for goal in active_goals:
        expired = False
        if goal.temporality == GoalTemporality.DAILY:
            # We assume it expires at the end of the created_at day
            if now.date() > goal.created_at.date():
                expired = True
        elif goal.temporality == GoalTemporality.WEEKLY:
            if (now.date() - goal.created_at.date()).days >= 7:
                expired = True
        elif goal.temporality == GoalTemporality.MONTHLY:
            if now.month != goal.created_at.month or now.year != goal.created_at.year:
                expired = True
        elif goal.temporality == GoalTemporality.ANNUAL:
            if now.year != goal.created_at.year:
                expired = True

        if expired:
            _process_goal_failure(db, goal, now)

    db.commit()


def _process_goal_failure(db: Session, goal: Goal, now: datetime):
    progress = get_goal_progress(goal, db)

    if progress >= goal.target_value:
        goal.state = GoalState.COMPLETED
        goal.is_completed = True
        goal.completed_at = now
        goal.current_value = progress
        return

    goal.state = GoalState.FAILED
    goal.current_value = progress

    new_goal = None
    if goal.fail_config == GoalFailConfig.ROLLOVER:
        new_goal = Goal(
            title=goal.title,
            description=goal.description,
            temporality=goal.temporality,
            measurement_type=goal.measurement_type,
            target_value=goal.target_value,
            current_value=0.0,
            state=GoalState.ACTIVE,
            fail_config=goal.fail_config,
            fail_emoji=goal.fail_emoji,
            color=goal.color,
            theme=goal.theme,
            note_id=goal.note_id,
            tag_id=goal.tag_id,
            parent_id=goal.parent_id or goal.id,
        )
        GoalRepository(db).add(new_goal)
    elif goal.fail_config == GoalFailConfig.SNOWBALL:
        shortfall = goal.target_value - progress
        new_target = goal.target_value + shortfall
        new_goal = Goal(
            title=goal.title,
            description=goal.description,
            temporality=goal.temporality,
            measurement_type=goal.measurement_type,
            target_value=new_target,
            current_value=0.0,
            state=GoalState.ACTIVE,
            fail_config=goal.fail_config,
            fail_emoji=goal.fail_emoji,
            color=goal.color,
            theme=goal.theme,
            note_id=goal.note_id,
            tag_id=goal.tag_id,
            parent_id=goal.parent_id or goal.id,
        )
        GoalRepository(db).add(new_goal)

    if new_goal:
        db.flush()
        try:
            from services.joidy_vault_writer import _write_goal_file, get_objectives_dir
            obj_dir = get_objectives_dir()
            if obj_dir:
                _write_goal_file(db, new_goal, obj_dir)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Failed to write rolled-over goal file: %s", e)


def get_goal_streak(db: Session) -> dict:
    """
    Calculate the current streak of consecutive days with at least one
    completed daily goal, counting backwards from today.
    Also returns the best (longest) streak ever.
    """
    completed_daily = (
        db.query(Goal)
        .filter(
            Goal.temporality == GoalTemporality.DAILY,
            Goal.state == GoalState.COMPLETED,
            Goal.completed_at.isnot(None),
        )
        .all()
    )

    # Build set of dates with completions
    completion_dates: set = set()
    for g in completed_daily:
        completion_dates.add(g.completed_at.date())

    if not completion_dates:
        return {"current_streak": 0, "best_streak": 0}

    # Current streak: count backwards from today
    today = datetime.utcnow().date()
    current_streak = 0
    day = today
    while day in completion_dates:
        current_streak += 1
        day -= timedelta(days=1)

    # Best streak: sort all dates and find longest consecutive run
    sorted_dates = sorted(completion_dates)
    best_streak = 1
    run = 1
    for i in range(1, len(sorted_dates)):
        if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
            run += 1
            best_streak = max(best_streak, run)
        else:
            run = 1

    return {"current_streak": current_streak, "best_streak": best_streak}
