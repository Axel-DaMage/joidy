"""Achievement Service — persistence and idempotent unlocking of achievements."""

import json

from models.achievement import Achievement
from sqlalchemy.orm import Session


def get_unlocked_achievements(db: Session, user_id: int) -> list[Achievement]:
    """Get every achievement unlocked by a user, oldest unlock first."""
    return db.query(Achievement).filter(Achievement.user_id == user_id).order_by(Achievement.unlocked_at.asc()).all()


def unlock_achievement(
    db: Session,
    user_id: int,
    achievement_key: str,
    unlocked_at=None,
    metadata: dict | None = None,
) -> tuple[Achievement, bool]:
    """Unlock an achievement idempotently.

    Returns ``(achievement, created)``: an already-unlocked key is returned
    unchanged (no duplicate row, original timestamp preserved).
    """
    existing = (
        db.query(Achievement)
        .filter(Achievement.user_id == user_id, Achievement.achievement_key == achievement_key)
        .first()
    )
    if existing:
        return existing, False

    record = Achievement(
        user_id=user_id,
        achievement_key=achievement_key,
        metadata_json=json.dumps(metadata) if metadata else "{}",
    )
    if unlocked_at is not None:
        record.unlocked_at = unlocked_at
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
