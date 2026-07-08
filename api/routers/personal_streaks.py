from datetime import date, timedelta

from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from models.personal_streaks import PersonalStreak, StreakCheckIn
from pydantic import BaseModel
from services.personal_streak_service import (
    backfill_streak_history,
    compute_streak,
)
from sqlalchemy.orm import Session, selectinload

router = APIRouter(prefix="/personal-streaks", tags=["personal-streaks"])

# ── Categories ─────────────────────────────────────────────────────────────────

CATEGORIES = ["general", "salud", "estudio", "fitness", "creatividad", "habito", "trabajo"]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _backfill_streak_history(db: Session, streak: PersonalStreak):
    """Generates missing check-ins from start_date up to yesterday."""
    if not streak.start_date:
        return

    today = date.today()
    end_date = streak.created_at.date() if streak.created_at else today
    current = streak.start_date

    # Get existing check-in dates to avoid duplicates
    existing_dates = {c.check_date for c in streak.checkins}

    added_count = 0
    while current < end_date:
        if current not in existing_dates:
            should_add = False
            if streak.frequency == "daily" or not streak.frequency:
                should_add = True
            elif streak.frequency == "every_n":
                days_since_start = (current - streak.start_date).days
                if days_since_start % (streak.frequency_days or 1) == 0:
                    should_add = True

            if should_add:
                ci = StreakCheckIn(
                    streak_id=streak.id,
                    check_date=current,
                    note="Auto-generado (Migración)"
                )
                db.add(ci)
                added_count += 1

        current += timedelta(days=1)

    if added_count > 0:
        streak.total_checkins = (streak.total_checkins or 0) + added_count
        db.commit()
        db.refresh(streak)


# ── Streak computation ─────────────────────────────────────────────────────────

def _compute_streak(checkin_dates: list[date], frequency: str = "daily", frequency_days: int = 1) -> tuple[int, int]:
    """Returns (current_streak, longest_streak) considering frequency settings."""
    if not checkin_dates:
        return 0, 0

    dates_set = set(checkin_dates)
    today = date.today()

    if frequency == "every_n" and frequency_days > 1:
        # For every-N-days: streak counts how many consecutive "on-time" check-ins
        sorted_dates = sorted(dates_set, reverse=True)
        current = 0
        # Walk from most recent check-in backwards
        for i, d in enumerate(sorted_dates):
            if i == 0:
                # Most recent must be within frequency_days of today
                if (today - d).days > frequency_days:
                    break
                current = 1
            else:
                gap = (sorted_dates[i - 1] - d).days
                if gap <= frequency_days:
                    current += 1
                else:
                    break

        # Longest streak
        sorted_asc = sorted(dates_set)
        longest = 1
        run = 1
        for i in range(1, len(sorted_asc)):
            gap = (sorted_asc[i] - sorted_asc[i - 1]).days
            if gap <= frequency_days:
                run += 1
                longest = max(longest, run)
            else:
                run = 1
        return current, max(longest, run) if sorted_asc else 0
    else:
        # Daily: original logic
        current = 0
        cursor = today

        # If today is not checked in, we should check yesterday.
        # The user still has time today to maintain the streak.
        if cursor not in dates_set:
            cursor -= timedelta(days=1)

        while cursor in dates_set:
            current += 1
            cursor -= timedelta(days=1)

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


def _streak_to_dict(streak: PersonalStreak, days_history: int = 365) -> dict:
    today = date.today()
    checkin_dates = [c.check_date for c in streak.checkins]
    checkin_map = {c.check_date: c for c in streak.checkins}
    current, longest = compute_streak(checkin_dates, streak.frequency or "daily", streak.frequency_days or 1)

    # Apply offset
    effective_current = current + streak.offset
    effective_longest = max(longest + streak.offset, streak.best_streak) if longest > 0 else max(streak.offset, streak.best_streak)

    # History for heatmap (last N days)
    history = []
    for i in range(days_history - 1, -1, -1):
        d = today - timedelta(days=i)
        checkin = checkin_map.get(d)
        entry = {
            "date": d.isoformat(),
            "checked": d in set(checkin_dates),
        }
        if checkin:
            entry["note"] = checkin.note or ""
            entry["mood"] = checkin.mood
        history.append(entry)

    # Days remaining to target
    days_remaining = None
    completion_pct = None
    if streak.target_date:
        days_remaining = max(0, (streak.target_date - today).days)
        if streak.start_date:
            total_span = (streak.target_date - streak.start_date).days
            elapsed = (today - streak.start_date).days
            completion_pct = min(100, round((elapsed / total_span) * 100)) if total_span > 0 else 100
        else:
            completion_pct = None

    # Total checkins from DB
    total_checkins = len(checkin_dates)

    return {
        "id": streak.id,
        "name": streak.name,
        "emoji": streak.emoji,
        "icon": streak.icon or "",
        "description": streak.description,
        "color": streak.color,
        "theme": streak.theme or "solid",
        "category": streak.category or "general",
        "start_date": streak.start_date.isoformat() if streak.start_date else None,
        "target_date": streak.target_date.isoformat() if streak.target_date else None,
        "offset": streak.offset,
        "frequency": streak.frequency or "daily",
        "frequency_days": streak.frequency_days or 1,
        "is_archived": streak.is_archived or False,
        "current_streak": effective_current,
        "longest_streak": effective_longest,
        "best_streak": streak.best_streak,
        "total_checkins": total_checkins,
        "freeze_count": streak.freeze_count,
        "freeze_used": streak.freeze_used or 0,
        "days_remaining": days_remaining,
        "completion_pct": completion_pct,
        "today_checked": today in set(checkin_dates),
        "history": history,
        "created_at": streak.created_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────

class StreakCreate(BaseModel):
    name: str
    emoji: str = "🔥"
    icon: str = ""
    description: str = ""
    color: str = ""
    theme: str = "solid"
    category: str = "general"
    start_date: date | None = None
    target_date: date | None = None
    offset: int = 0
    frequency: str = "daily"
    frequency_days: int = 1
    freeze_count: int = 0


class StreakUpdate(BaseModel):
    name: str | None = None
    emoji: str | None = None
    icon: str | None = None
    description: str | None = None
    color: str | None = None
    theme: str | None = None
    category: str | None = None
    start_date: date | None = None
    target_date: date | None = None
    offset: int | None = None
    frequency: str | None = None
    frequency_days: int | None = None
    is_archived: bool | None = None
    freeze_count: int | None = None


class CheckInData(BaseModel):
    note: str = ""
    mood: int | None = None
    check_date: date | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/categories")
def list_categories():
    return CATEGORIES


@router.get("/stats")
def global_stats(db: Session = Depends(get_db)):
    """Global streak statistics."""
    all_streaks = db.query(PersonalStreak).options(selectinload(PersonalStreak.checkins)).all()
    active = [s for s in all_streaks if not s.is_archived]
    archived = [s for s in all_streaks if s.is_archived]

    # Compute stats
    longest_ever = 0
    longest_name = ""
    total_checkins = 0

    for s in all_streaks:
        checkin_dates = [c.check_date for c in s.checkins]
        _, longest = compute_streak(checkin_dates, s.frequency or "daily", s.frequency_days or 1)
        effective = longest + s.offset
        if effective > longest_ever:
            longest_ever = effective
            longest_name = s.name
        total_checkins += len(checkin_dates)

    # Check-in rate for active streaks in last 30 days
    today = date.today()
    thirty_ago = today - timedelta(days=30)
    possible_checkins = 0
    actual_checkins = 0
    for s in active:
        freq_days = s.frequency_days or 1
        possible_checkins += 30 // freq_days
        actual_checkins += sum(1 for c in s.checkins if c.check_date >= thirty_ago)

    checkin_rate = round((actual_checkins / possible_checkins) * 100) if possible_checkins > 0 else 0

    # Days tracked (from earliest start_date or created_at)
    earliest = today
    for s in all_streaks:
        if s.start_date and s.start_date < earliest:
            earliest = s.start_date
        elif s.created_at and s.created_at.date() < earliest:
            earliest = s.created_at.date()
    days_tracked = (today - earliest).days if all_streaks else 0

    return {
        "total_active": len(active),
        "total_archived": len(archived),
        "longest_ever": longest_ever,
        "longest_name": longest_name,
        "total_checkins": total_checkins,
        "checkin_rate": checkin_rate,
        "days_tracked": days_tracked,
    }


@router.get("/")
def list_streaks(
    include_archived: bool = Query(False),
    category: str | None = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(PersonalStreak).options(selectinload(PersonalStreak.checkins))
    if not include_archived:
        q = q.filter(PersonalStreak.is_archived == False)
    if category and category != "all":
        q = q.filter(PersonalStreak.category == category)
    streaks = q.order_by(PersonalStreak.created_at).all()
    return [_streak_to_dict(s) for s in streaks]


@router.post("/", status_code=201)
def create_streak(data: StreakCreate, db: Session = Depends(get_db)):
    streak = PersonalStreak(
        name=data.name.strip(),
        emoji=data.emoji,
        icon=data.icon,
        description=data.description,
        color=data.color,
        theme=data.theme,
        category=data.category,
        start_date=data.start_date or date.today(),
        target_date=data.target_date,
        offset=data.offset,
        frequency=data.frequency,
        frequency_days=max(1, data.frequency_days),
        freeze_count=data.freeze_count,
    )
    db.add(streak)
    db.commit()
    db.refresh(streak)

    # Automatically backfill if start_date is in the past
    if streak.start_date and streak.start_date < date.today():
        backfill_streak_history(db, streak)

    return _streak_to_dict(streak)


@router.put("/{streak_id}")
def update_streak(streak_id: int, data: StreakUpdate, db: Session = Depends(get_db)):
    streak = db.query(PersonalStreak).filter(PersonalStreak.id == streak_id).first()
    if not streak:
        raise HTTPException(status_code=404, detail="Streak not found")

    updatable = [
        "name", "emoji", "icon", "description", "color", "theme", "category",
        "target_date", "frequency", "frequency_days",
        "is_archived", "freeze_count",
    ]
    for field in updatable:
        val = getattr(data, field, None)
        if val is not None:
            if field == "name":
                val = val.strip()
            if field == "frequency_days":
                val = max(1, val)
            setattr(streak, field, val)

    db.commit()
    db.refresh(streak)

    # If start_date was moved back, backfill again
    if streak.start_date and streak.start_date < date.today():
        backfill_streak_history(db, streak)

    return _streak_to_dict(streak)


@router.delete("/{streak_id}", status_code=204)
def delete_streak(streak_id: int, db: Session = Depends(get_db)):
    streak = db.query(PersonalStreak).filter(PersonalStreak.id == streak_id).first()
    if not streak:
        raise HTTPException(status_code=404, detail="Streak not found")
    db.delete(streak)
    db.commit()


@router.post("/{streak_id}/checkin")
def checkin(streak_id: int, data: CheckInData = None, db: Session = Depends(get_db)):
    if data is None:
        data = CheckInData()

    streak = db.query(PersonalStreak).filter(PersonalStreak.id == streak_id).first()
    if not streak:
        raise HTTPException(status_code=404, detail="Streak not found")

    today = data.check_date or date.today()
    existing = db.query(StreakCheckIn).filter(
        StreakCheckIn.streak_id == streak_id,
        StreakCheckIn.check_date == today,
    ).first()

    if existing:
        # Update existing check-in note/mood
        if data.note:
            existing.note = data.note
        if data.mood is not None:
            existing.mood = data.mood
        db.commit()
    else:
        ci = StreakCheckIn(
            streak_id=streak_id,
            check_date=today,
            note=data.note,
            mood=data.mood,
        )
        db.add(ci)
        streak.total_checkins = (streak.total_checkins or 0) + 1
        db.commit()

    db.refresh(streak)

    # Update best_streak if current surpasses it
    result = _streak_to_dict(streak)
    if result["current_streak"] > streak.best_streak:
        streak.best_streak = result["current_streak"]
        db.commit()
        db.refresh(streak)
        result = _streak_to_dict(streak)

    return result


@router.delete("/{streak_id}/checkin", status_code=200)
def undo_checkin(streak_id: int, db: Session = Depends(get_db)):
    streak = db.query(PersonalStreak).filter(PersonalStreak.id == streak_id).first()
    if not streak:
        raise HTTPException(status_code=404, detail="Streak not found")

    today = date.today()
    ci = db.query(StreakCheckIn).filter(
        StreakCheckIn.streak_id == streak_id,
        StreakCheckIn.check_date == today,
    ).first()

    if ci:
        db.delete(ci)
        streak.total_checkins = max(0, (streak.total_checkins or 0) - 1)
        db.commit()
        db.refresh(streak)

    return _streak_to_dict(streak)


@router.post("/{streak_id}/freeze")
def use_freeze(streak_id: int, db: Session = Depends(get_db)):
    """Use a freeze to protect the streak for today."""
    streak = db.query(PersonalStreak).filter(PersonalStreak.id == streak_id).first()
    if not streak:
        raise HTTPException(status_code=404, detail="Streak not found")

    available = (streak.freeze_count or 0) - (streak.freeze_used or 0)
    if available <= 0:
        raise HTTPException(status_code=400, detail="No freezes available")

    # Check if already checked in today
    today = date.today()
    already = db.query(StreakCheckIn).filter(
        StreakCheckIn.streak_id == streak_id,
        StreakCheckIn.check_date == today,
    ).first()

    if already:
        raise HTTPException(status_code=400, detail="Already checked in today")

    # Create a freeze check-in (marked with special note)
    ci = StreakCheckIn(
        streak_id=streak_id,
        check_date=today,
        note="❄️ Freeze usado",
        mood=None,
    )
    db.add(ci)
    streak.freeze_used = (streak.freeze_used or 0) + 1
    db.commit()
    db.refresh(streak)

    return _streak_to_dict(streak)


@router.get("/{streak_id}/history")
def get_history(
    streak_id: int,
    days: int = Query(90, ge=7, le=365),
    db: Session = Depends(get_db),
):
    """Get detailed check-in history for a streak."""
    streak = db.query(PersonalStreak).filter(PersonalStreak.id == streak_id).first()
    if not streak:
        raise HTTPException(status_code=404, detail="Streak not found")

    today = date.today()
    since = today - timedelta(days=days)
    checkins = (
        db.query(StreakCheckIn)
        .filter(
            StreakCheckIn.streak_id == streak_id,
            StreakCheckIn.check_date >= since,
        )
        .order_by(StreakCheckIn.check_date.desc())
        .all()
    )

    return [
        {
            "date": c.check_date.isoformat(),
            "note": c.note or "",
            "mood": c.mood,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in checkins
    ]
