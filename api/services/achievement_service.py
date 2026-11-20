"""Achievement Service — persistence and idempotent unlocking of achievements.

Unlock integrity (#1320): ``/achievements/unlock`` used to trust whatever
``achievement_key``/``unlocked_at`` the client sent. Keys are now validated
against a server-side catalog whose preconditions are checked against real
state — a client cannot mint an achievement it has not earned, cannot
backdate ``unlocked_at``, and metadata is size-bounded at the router.
"""

import json
from collections.abc import Callable

from models.achievement import Achievement
from models.gamification import UserStats
from models.goal import Goal, GoalState
from models.note import Note, Tag
from models.skill import Skill
from sqlalchemy.orm import Session

MAX_METADATA_BYTES = 2000


class UnknownAchievementKeyError(ValueError):
    """Raised when the client requests a key absent from the catalog."""


class AchievementCriteriaNotMetError(ValueError):
    """Raised when a catalog achievement's server-side precondition fails."""


def _note_count_at_least(db: Session, threshold: int) -> bool:
    return db.query(Note).count() >= threshold


def _streak_at_least(db: Session, days: int) -> bool:
    stats = db.query(UserStats).first()
    if stats is None:
        return False
    return max(stats.current_streak or 0, stats.longest_streak or 0) >= days


def _plant_stage_at_least(db: Session, stage: int) -> bool:
    stats = db.query(UserStats).first()
    return stats is not None and (stats.plant_stage or 0) >= stage


# Server-side catalog mirroring the frontend's ACHIEVEMENTS_CONFIG
# (frontend/src/lib/stores/achievements.ts). Each verifier checks the real
# precondition; unlocking a catalog key without meeting it is rejected.
ACHIEVEMENT_CATALOG: dict[str, Callable[[Session], bool]] = {
    "first_note": lambda db: _note_count_at_least(db, 1),
    "ten_notes": lambda db: _note_count_at_least(db, 10),
    "fifty_notes": lambda db: _note_count_at_least(db, 50),
    "first_goal": lambda db: db.query(Goal).count() >= 1,
    "goal_completed": lambda db: (
        db.query(Goal).filter(Goal.is_completed.is_(True) | (Goal.state == GoalState.COMPLETED)).first() is not None
    ),
    "week_streak": lambda db: _streak_at_least(db, 7),
    "month_streak": lambda db: _streak_at_least(db, 30),
    "first_tag": lambda db: db.query(Tag).count() >= 1,
    "ten_skills": lambda db: db.query(Skill).filter(Skill.first_unlocked_at.isnot(None)).count() >= 10,
    "plant_sprout": lambda db: _plant_stage_at_least(db, 1),
    "plant_tree": lambda db: _plant_stage_at_least(db, 6),
}


def get_unlocked_achievements(db: Session, user_id: int) -> list[Achievement]:
    """Get every achievement unlocked by a user, oldest unlock first."""
    return db.query(Achievement).filter(Achievement.user_id == user_id).order_by(Achievement.unlocked_at.asc()).all()


def unlock_achievement(
    db: Session,
    user_id: int,
    achievement_key: str,
    metadata: dict | None = None,
) -> tuple[Achievement, bool]:
    """Unlock an achievement idempotently.

    Returns ``(achievement, created)``: an already-unlocked key is returned
    unchanged (no duplicate row, original timestamp preserved). New unlocks
    must be catalog-defined and pass the server-side precondition —
    ``unlocked_at`` is always stamped by the server, never by the client.
    """
    existing = (
        db.query(Achievement)
        .filter(Achievement.user_id == user_id, Achievement.achievement_key == achievement_key)
        .first()
    )
    if existing:
        return existing, False

    verifier = ACHIEVEMENT_CATALOG.get(achievement_key)
    if verifier is None:
        raise UnknownAchievementKeyError(achievement_key)
    if not verifier(db):
        raise AchievementCriteriaNotMetError(achievement_key)

    record = Achievement(
        user_id=user_id,
        achievement_key=achievement_key,
        metadata_json=json.dumps(metadata) if metadata else "{}",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record, True


def serialize_achievement(record: Achievement) -> dict:
    try:
        metadata = json.loads(record.metadata_json) if record.metadata_json else {}
    except json.JSONDecodeError:
        metadata = {}
    return {
        "id": record.id,
        "user_id": record.user_id,
        "achievement_key": record.achievement_key,
        "unlocked_at": record.unlocked_at.isoformat() if record.unlocked_at else None,
        "metadata": metadata,
    }
