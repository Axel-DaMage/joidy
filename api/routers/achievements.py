import json
from datetime import datetime
from typing import Any

from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from services.achievement_service import (
    MAX_METADATA_BYTES,
    AchievementCriteriaNotMetError,
    UnknownAchievementKeyError,
    get_unlocked_achievements,
    serialize_achievement,
    unlock_achievement,
)
from services.auth_service import get_current_user
from sqlalchemy.orm import Session

router = APIRouter(prefix="/achievements", tags=["achievements"])


class AchievementUnlock(BaseModel):
    achievement_key: str = Field(min_length=1, max_length=100)
    # Accepted for backward compatibility but ignored since #1320 — the
    # server stamps ``unlocked_at`` itself; client-supplied timestamps are
    # never persisted.
    unlocked_at: datetime | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("metadata")
    @classmethod
    def metadata_is_bounded(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        if v is not None and len(json.dumps(v, default=str)) > MAX_METADATA_BYTES:
            raise ValueError(f"metadata exceeds {MAX_METADATA_BYTES} bytes")
        return v


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
    """Unlock an achievement (idempotent — replaying a key is a no-op).

    The key must exist in the server-side catalog and its precondition must
    be verifiably met (#1320): unknown keys are rejected with 400 and
    unearned catalog keys with 403.
    """
    try:
        record, created = unlock_achievement(db, user_id, data.achievement_key, data.metadata)
    except UnknownAchievementKeyError:
        raise HTTPException(status_code=400, detail="Unknown achievement key") from None
    except AchievementCriteriaNotMetError:
        raise HTTPException(status_code=403, detail="Achievement criteria not met") from None
    return {**serialize_achievement(record), "already_unlocked": not created}
