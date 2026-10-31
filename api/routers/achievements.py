from datetime import datetime
from typing import Any

from database import get_db
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from services.achievement_service import (
    get_unlocked_achievements,
    serialize_achievement,
    unlock_achievement,
)
from services.auth_service import get_current_user
from sqlalchemy.orm import Session

router = APIRouter(prefix="/achievements", tags=["achievements"])


class AchievementUnlock(BaseModel):
    achievement_key: str = Field(min_length=1, max_length=100)
    unlocked_at: datetime | None = None
    metadata: dict[str, Any] | None = None


@router.get("/")
def list_achievements(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    """List the achievements unlocked by the authenticated user."""
    records = get_unlocked_achievements(db, user_id)
    return [serialize_achievement(r) for r in records]


@router.post("/unlock")
def unlock(
    data: AchievementUnlock,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    """Unlock an achievement (idempotent — replaying a key is a no-op)."""
    record, created = unlock_achievement(db, user_id, data.achievement_key, data.unlocked_at, data.metadata)
    return {**serialize_achievement(record), "already_unlocked": not created}
