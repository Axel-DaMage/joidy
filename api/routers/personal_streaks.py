from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.personal_streaks import PersonalStreak, StreakCheckIn

router = APIRouter(prefix="/personal-streaks", tags=["personal-streaks"])


# ── Streak computation ─────────────────────────────────────────────────────────

def _compute_streak(checkin_dates: list[date]) -> tuple[int, int]:
    """Returns (current_streak, longest_streak) from a list of check-in dates."""
    if not checkin_dates:
        return 0, 0

    dates_set = set(checkin_dates)
    today = date.today()

    # Current streak: walk backwards from today
    current = 0
    cursor = today
    while cursor in dates_set:
        current += 1
        cursor -= timedelta(days=1)

    # Longest streak: scan sorted dates
    sorted_dates = sorted(dates_set)
    longest = 1
    run = 1
    for i in range(1, len(sorted_dates)):
        if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
            run += 1
            longest = max(longest, run)
        else:
            run = 1
    longest = max(longest, run) if sorted_dates else 0

    return current, longest


def _streak_to_dict(streak: PersonalStreak, days_history: int = 30) -> dict:
    today = date.today()
    checkin_dates = [c.check_date for c in streak.checkins]
    current, longest = _compute_streak(checkin_dates)

    # Last N days for mini-calendar
    history = []
    for i in range(days_history - 1, -1, -1):
        d = today - timedelta(days=i)
        history.append({
            "date": d.isoformat(),
            "checked": d in set(checkin_dates),
        })

    return {
        "id": streak.id,
        "name": streak.name,
        "emoji": streak.emoji,
        "description": streak.description,
        "current_streak": current,
        "longest_streak": longest,
        "today_checked": today in set(checkin_dates),
        "history": history,
        "created_at": streak.created_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class StreakCreate(BaseModel):
    name: str
    emoji: str = "🔥"
    description: str = ""


class StreakUpdate(BaseModel):
    name: Optional[str] = None
    emoji: Optional[str] = None
    description: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/")
def list_streaks(db: Session = Depends(get_db)):
    streaks = db.query(PersonalStreak).order_by(PersonalStreak.created_at).all()
    return [_streak_to_dict(s) for s in streaks]


@router.post("/", status_code=201)
def create_streak(data: StreakCreate, db: Session = Depends(get_db)):
    streak = PersonalStreak(name=data.name.strip(), emoji=data.emoji, description=data.description)
    db.add(streak)
    db.commit()
    db.refresh(streak)
    return _streak_to_dict(streak)


@router.put("/{streak_id}")
def update_streak(streak_id: int, data: StreakUpdate, db: Session = Depends(get_db)):
    streak = db.query(PersonalStreak).filter(PersonalStreak.id == streak_id).first()
    if not streak:
        raise HTTPException(status_code=404, detail="Streak not found")
    if data.name is not None:
        streak.name = data.name.strip()
    if data.emoji is not None:
        streak.emoji = data.emoji
    if data.description is not None:
        streak.description = data.description
    db.commit()
    db.refresh(streak)
    return _streak_to_dict(streak)


@router.delete("/{streak_id}", status_code=204)
def delete_streak(streak_id: int, db: Session = Depends(get_db)):
    streak = db.query(PersonalStreak).filter(PersonalStreak.id == streak_id).first()
    if not streak:
        raise HTTPException(status_code=404, detail="Streak not found")
    db.delete(streak)
    db.commit()


@router.post("/{streak_id}/checkin")
def checkin(streak_id: int, db: Session = Depends(get_db)):
    streak = db.query(PersonalStreak).filter(PersonalStreak.id == streak_id).first()
    if not streak:
        raise HTTPException(status_code=404, detail="Streak not found")

    today = date.today()
    existing = db.query(StreakCheckIn).filter(
        StreakCheckIn.streak_id == streak_id,
        StreakCheckIn.check_date == today,
    ).first()

    if not existing:
        db.add(StreakCheckIn(streak_id=streak_id, check_date=today))
        db.commit()
        db.refresh(streak)

    return _streak_to_dict(streak)


@router.delete("/{streak_id}/checkin", status_code=200)
def undo_checkin(streak_id: int, db: Session = Depends(get_db)):
    streak = db.query(PersonalStreak).filter(PersonalStreak.id == streak_id).first()
    if not streak:
        raise HTTPException(status_code=404, detail="Streak not found")

    today = date.today()
    checkin = db.query(StreakCheckIn).filter(
        StreakCheckIn.streak_id == streak_id,
        StreakCheckIn.check_date == today,
    ).first()

    if checkin:
        db.delete(checkin)
        db.commit()
        db.refresh(streak)

    return _streak_to_dict(streak)
