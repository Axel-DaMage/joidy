from database import get_db
from fastapi import APIRouter, Depends, Query
from models.mood_entry import MoodEntry
from pydantic import BaseModel, field_validator
from services.auth_service import get_current_user
from services.mood_service import (
    create_or_update_mood,
    get_mood_history,
    get_mood_stats,
    get_today_mood,
)
from sqlalchemy.orm import Session

router = APIRouter(prefix="/mood", tags=["mood"])


class MoodCreate(BaseModel):
    """Schema for creating/updating today's mood."""

    score: int
    note: str | None = None

    @field_validator("score")
    @classmethod
    def score_range(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError("score must be between 1 and 5")
        return v


def _serialize_mood(entry: MoodEntry) -> dict:
    return {
        "id": entry.id,
        "user_id": entry.user_id,
        "score": entry.score,
        "note": entry.note,
        "entry_date": entry.entry_date.isoformat(),
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
    }


@router.post("/")
def create_mood(
    data: MoodCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    """Create or update today's mood entry."""
    entry = create_or_update_mood(db, user_id, data.score, data.note)
    return _serialize_mood(entry)


@router.get("/today")
def get_today(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    """Get today's mood entry, or null if not yet recorded."""
    entry = get_today_mood(db, user_id)
    if not entry:
        return None
    return _serialize_mood(entry)


@router.get("/history")
def get_history(
    days: int = Query(30, ge=1, le=366),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    """Get mood history for the last N days (oldest → newest)."""
    entries = get_mood_history(db, user_id, days)
    return [_serialize_mood(e) for e in entries]


@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    """Get mood statistics: average, streak, total entries, notes correlation."""
    return get_mood_stats(db, user_id)
