"""
Gamification Engine — the heart of Joidy's dopamine loop.

Every mutation in the system calls process_event(), which:
1. Awards XP
2. Updates the streak
3. Recalculates the plant stage
4. Returns a GamificationResult for the frontend to animate
"""

import json
import logging
from dataclasses import dataclass
from datetime import date

from config import settings
from models.config import SystemConfig
from models.gamification import StreakRecord, UserStats, XPEvent
from services.response_cache import clear_api_caches
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

DEFAULT_XP_TABLE = {
    "note_created": 10,
    "note_edited": 5,
    "tag_added": 3,
    "tag_accepted_ai": 4,
    "topic_connected": 8,
    "goal_completed": 50,
    "daily_activity": 15,
    "streak_milestone_7": 100,
    "streak_milestone_30": 100,
    "streak_milestone_100": 100,
    "note_imported_obsidian": 2,
}

DEFAULT_PLANT_STAGES = [
    (0,     "semilla"),
    (300,   "brote"),
    (1200,  "plantón"),
    (4000,  "joven"),
    (10000, "madura"),
    (25000, "floreciendo"),
    (60000, "árbol"),
]


def load_config_from_db(db: Session) -> dict[str, str]:
    """Load config from database, returns key-value dict."""
    try:
        configs = db.query(SystemConfig).all()
        return {c.key: c.value for c in configs}
    except Exception:
        logger.warning("Failed to load system_config from DB, using defaults")
        return {}


def get_xp_table_from_db(db: Session) -> dict[str, int]:
    """Get XP table from database config."""
    config = load_config_from_db(db)
    result = {}
    for key, default_value in DEFAULT_XP_TABLE.items():
        db_key = f"xp_{key}"
        try:
            result[key] = int(config.get(db_key, default_value))
        except (ValueError, TypeError):
            result[key] = default_value
    return result


def get_plant_stages_from_db(db: Session) -> list[tuple[int, str]]:
    """Get plant stages from database config."""
    config = load_config_from_db(db)
    stages = []
    for i in range(7):
        key = f"plant_stage_{i}"
        try:
            threshold = int(config.get(key, DEFAULT_PLANT_STAGES[i][0]))
            name = config.get(f"plant_stage_{i}_name", DEFAULT_PLANT_STAGES[i][1])
            stages.append((threshold, name))
        except (ValueError, TypeError, IndexError):
            stages.append(DEFAULT_PLANT_STAGES[i])
    return sorted(stages, key=lambda x: x[0])


_xp_table_cache: dict[str, int] | None = None
_plant_stages_cache: list[tuple[int, str]] | None = None


def get_xp_table(db: Session | None = None) -> dict[str, int]:
    """Get XP table - from DB if available, else env var, else defaults."""
    global _xp_table_cache

    # Try env var override first (for quick testing)
    if settings.xp_table_json:
        try:
            parsed = json.loads(settings.xp_table_json)
            if isinstance(parsed, dict):
                merged = dict(DEFAULT_XP_TABLE)
                for key, value in parsed.items():
                    if isinstance(key, str) and isinstance(value, int):
                        merged[key] = value
                _xp_table_cache = merged
                return merged
        except Exception:
            pass

    # Try database config
    if db:
        try:
            config = get_xp_table_from_db(db)
            _xp_table_cache = config
            return config
        except Exception:
            pass

    # Fallback to cached defaults
    if _xp_table_cache is None:
        _xp_table_cache = dict(DEFAULT_XP_TABLE)
    return _xp_table_cache


def get_plant_stages(db: Session | None = None) -> list[tuple[int, str]]:
    """Get plant stages - from DB if available, else defaults."""
    global _plant_stages_cache

    if db:
        try:
            stages = get_plant_stages_from_db(db)
            _plant_stages_cache = stages
            return stages
        except Exception:
            pass

    if _plant_stages_cache is None:
        _plant_stages_cache = list(DEFAULT_PLANT_STAGES)
    return _plant_stages_cache


def xp_for(event_type: str, db: Session | None = None, fallback: int = 0) -> int:
    return get_xp_table(db).get(event_type, fallback)


PLANT_STAGES = DEFAULT_PLANT_STAGES  # Default fallback

STREAK_MILESTONES = {7, 30, 100, 365}
GRACE_PERIOD_DAYS = 1  # One missed day forgiven per week


@dataclass
class GamificationResult:
    xp_awarded: int = 0
    total_xp: int = 0
    current_streak: int = 0
    plant_stage: int = 0
    plant_stage_name: str = "seed"
    plant_stage_changed: bool = False
    streak_changed: bool = False
    milestone_reached: int | None = None
    new_skill_unlocked: str | None = None
    message: str = ""


def _get_or_create_stats(db: Session) -> UserStats:
    stats = db.query(UserStats).filter(UserStats.id == 1).first()
    if not stats:
        stats = UserStats(id=1)
        db.add(stats)
        db.flush()
    return stats


def _compute_plant_stage(total_xp: int, db: Session | None = None) -> tuple[int, str]:
    stages = get_plant_stages(db)
    stage_idx = 0
    for i, (threshold, name) in enumerate(stages):
        if total_xp >= threshold:
            stage_idx = i
    return stage_idx, stages[stage_idx][1]


def _compute_streak(db: Session, stats: UserStats) -> tuple[int, bool]:
    today = date.today()
    last = stats.last_activity_date

    if last is None:
        return 1, True  # First-ever activity: start streak at 1

    if last == today:
        return stats.current_streak, False

    days_since = (today - last).days
    if days_since == 1:
        # Consecutive day — streak continues
        new_streak = stats.current_streak + 1
    elif days_since <= GRACE_PERIOD_DAYS + 1:
        # Grace period — don't break streak, but don't increment
        new_streak = stats.current_streak
    else:
        # Streak broken
        new_streak = 1

    return new_streak, new_streak != stats.current_streak


def process_event(
    db: Session,
    event_type: str,
    metadata: dict | None = None,
) -> GamificationResult:
    xp = xp_for(event_type, db, 0)
    if metadata is None:
        metadata = {}

    stats = _get_or_create_stats(db)
    today = date.today()

    # Check if already at max XP
    stages = get_plant_stages(db)
    max_xp = stages[-1][0] if stages else DEFAULT_PLANT_STAGES[-1][0]

    if stats.total_xp >= max_xp:
        stage_idx, stage_name = _compute_plant_stage(stats.total_xp, db)
        return GamificationResult(
            xp_awarded=0,
            total_xp=stats.total_xp,
            current_streak=stats.current_streak,
            plant_stage=stage_idx,
            plant_stage_name=stage_name,
            plant_stage_changed=False,
            streak_changed=False,
            milestone_reached=None,
            message="¡Ya has alcanzado el máximo de XP! 🌟",
        )

    # daily_activity is idempotent — only award XP once per day
    if event_type == "daily_activity" and stats.last_activity_date == today:
        # Heal: if active today but streak is 0, it was written by the old buggy engine
        if stats.current_streak == 0:
            stats.current_streak = 1
            if stats.longest_streak < 1:
                stats.longest_streak = 1
            db.commit()
            db.refresh(stats)
        stage_idx, stage_name = _compute_plant_stage(stats.total_xp, db)
        return GamificationResult(
            xp_awarded=0,
            total_xp=stats.total_xp,
            current_streak=stats.current_streak,
            plant_stage=stage_idx,
            plant_stage_name=stage_name,
            message="",
        )

    # Record XP event
    event = XPEvent(event_type=event_type, xp=xp, metadata_json=json.dumps(metadata))
    db.add(event)

    old_plant_stage = stats.plant_stage

    # Add XP
    stats.total_xp += xp

    # Update streak
    new_streak, streak_changed = _compute_streak(db, stats)
    is_new_day = stats.last_activity_date != today

    if is_new_day:
        stats.current_streak = new_streak
        stats.last_activity_date = today
        # Record activity for this day
        existing = db.query(StreakRecord).filter(StreakRecord.activity_date == today).first()
        if not existing:
            db.add(StreakRecord(activity_date=today, xp_earned=xp))
            # Award daily activity bonus only if not already the daily_activity event
            if event_type != "daily_activity":
                daily_xp = xp_for("daily_activity", db, 15)
                stats.total_xp += daily_xp
                xp += daily_xp
                db.add(XPEvent(event_type="daily_activity", xp=daily_xp))
        if new_streak > stats.longest_streak:
            stats.longest_streak = new_streak
    else:
        existing_streak_record = db.query(StreakRecord).filter(
            StreakRecord.activity_date == today
        ).first()
        if existing_streak_record:
            existing_streak_record.xp_earned += xp

    # Check streak milestones
    milestone_reached = None
    if is_new_day and new_streak in STREAK_MILESTONES:
        milestone_xp = xp_for(f"streak_milestone_{new_streak}", db, 100)
        stats.total_xp += milestone_xp
        xp += milestone_xp
        db.add(XPEvent(event_type=f"streak_milestone_{new_streak}", xp=milestone_xp))
        milestone_reached = new_streak

    # Update plant stage
    new_stage, new_stage_name = _compute_plant_stage(stats.total_xp, db)
    stats.plant_stage = new_stage
    plant_stage_changed = new_stage != old_plant_stage

    db.commit()
    db.refresh(stats)
    clear_api_caches()

    # Centralized WebSocket broadcasts for gamification
    try:
        from routers.websocket import broadcast_streak_updated, broadcast_xp_gained
        if xp > 0:
            broadcast_xp_gained(xp, stats.total_xp)
        if streak_changed:
            broadcast_streak_updated(new_streak)
    except Exception as e:
        logger.error(f"Failed to broadcast gamification event: {e}")

    return GamificationResult(
        xp_awarded=xp,
        total_xp=stats.total_xp,
        current_streak=stats.current_streak,
        plant_stage=new_stage,
        plant_stage_name=new_stage_name,
        plant_stage_changed=plant_stage_changed,
        streak_changed=streak_changed,
        milestone_reached=milestone_reached,
        message=_build_message(event_type, xp, new_stage_name, milestone_reached, plant_stage_changed),
    )


def _build_message(
    event_type: str, xp: int, stage_name: str, milestone: int | None, stage_changed: bool
) -> str:
    parts = [f"+{xp} XP"]
    if stage_changed:
        parts.append(f"Tu planta creció: {stage_name}!")
    if milestone:
        parts.append(f"{milestone} días de racha!")
    return " · ".join(parts)
