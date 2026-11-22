from datetime import date, timedelta

from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from models.personal_streaks import PersonalStreak, StreakCheckIn
from pydantic import BaseModel, ConfigDict, Field, field_validator
from services.pagination import add_pagination_headers
from services.personal_streak_service import (
    backfill_streak_history,
    compute_streak,
)
from services.timezone_utils import get_local_today
from sqlalchemy.orm import Session, selectinload

router = APIRouter(prefix="/personal-streaks", tags=["personal-streaks"])

# ── Categories ─────────────────────────────────────────────────────────────────

CATEGORIES = ["general", "salud", "estudio", "fitness", "creatividad", "habito", "trabajo"]

# ── Input validation bounds (#1321) ─────────────────────────────────────────────
#
# Streak dates are clamped to a sane window. An absurdly old start_date such as
# 0001-01-01 used to drive the backfill loop through ~740k day-iterations (one
# StreakCheckIn insert per day) inside a single request — a DoS plus DB bloat.
# - start_date: up to ~5 years back (streak history) and up to ~1 year ahead
#   (the UI deliberately allows scheduling a future start; no backfill runs).
# - check_date: same past window; +1 day future tolerance because the frontend
#   sends the browser-local date, which can legitimately sit one day ahead of
#   the server-side configured timezone (see #864).
# The service layer additionally caps each backfill at MAX_BACKFILL_DAYS.

MAX_STREAK_HISTORY_DAYS = 5 * 366  # ~5 years (leap-safe upper bound)
MAX_START_DATE_FUTURE_DAYS = 366
MAX_CHECKIN_FUTURE_DAYS = 1
MAX_OFFSET_DAYS = 36500  # ~100y — keeps migrations from other trackers possible
MAX_FREEZE_COUNT = 30  # matches the create/edit modal's own max
MAX_FREQUENCY_DAYS = 365  # matches the modal's every-N-days input bounds
VALID_FREQUENCIES = {"daily", "weekly", "monthly", "every_n"}


def _validate_date_window(v: date | None, *, max_future_days: int, field: str) -> date | None:
    """Reject dates outside [today - MAX_STREAK_HISTORY_DAYS, today + max_future_days]."""
    if v is None:
        return v
    today = get_local_today()
    if v < today - timedelta(days=MAX_STREAK_HISTORY_DAYS):
        raise ValueError(f"{field} cannot be more than ~5 years in the past")
    if v > today + timedelta(days=max_future_days):
        if max_future_days <= 1:
            raise ValueError(f"{field} cannot be in the future")
        raise ValueError(f"{field} cannot be more than ~1 year in the future")
    return v


def _normalize_frequency(v: str | None) -> str | None:
    """Canonicalize frequency (case/space-tolerant) and enforce the allowed set."""
    if v is None:
        return v
    v = v.strip().lower()
    if v not in VALID_FREQUENCIES:
        raise ValueError(f"frequency must be one of: {', '.join(sorted(VALID_FREQUENCIES))}")
    return v


def _require_nonblank_name(v: str | None) -> str | None:
    if v is None:
        return v
    v = v.strip()
    if not v:
        raise ValueError("name cannot be empty")
    return v


def _streak_to_dict(streak: PersonalStreak, days_history: int = 365) -> dict:
    today = get_local_today()
    checkin_dates = [c.check_date for c in streak.checkins]
    checkin_map = {c.check_date: c for c in streak.checkins}
    current, longest = compute_streak(
        checkin_dates,
        streak.frequency or "daily",
        streak.frequency_days or 1,
        snowball_mode=bool(getattr(streak, "snowball_mode", False)),
    )

    # Apply offset
    effective_current = current + streak.offset
    effective_longest = (
        max(longest + streak.offset, streak.best_streak) if longest > 0 else max(streak.offset, streak.best_streak)
    )

    # Timezone-safe "today" reference: if the server's UTC today is not in
    # the check-in set but the most recent check-in is within 1 day, use it
    # as the reference for today_checked and history. See issue #864.
    dates_set = set(checkin_dates)
    if dates_set:
        most_recent = max(dates_set)
        # Use most_recent as "today" if it's within 1 day of server-today
        # (handles UTC offset where user's local date differs from server).
        if today not in dates_set and abs((today - most_recent).days) <= 1:
            effective_today = most_recent
        else:
            effective_today = today
    else:
        effective_today = today

    # History for heatmap (last N days)
    history = []
    if days_history > 0:
        for i in range(days_history - 1, -1, -1):
            d = effective_today - timedelta(days=i)
            checkin = checkin_map.get(d)
            entry = {
                "date": d.isoformat(),
                "checked": d in dates_set,
            }
            if checkin:
                entry["note"] = checkin.note or ""
                entry["mood"] = checkin.mood
            history.append(entry)

    # Days remaining to target
    days_remaining = None
    completion_pct = None
    if streak.target_date:
        days_remaining = max(0, (streak.target_date - effective_today).days)
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
        "snowball_mode": bool(getattr(streak, "snowball_mode", False)),
        "is_archived": streak.is_archived or False,
        "current_streak": effective_current,
        "longest_streak": effective_longest,
        "best_streak": streak.best_streak,
        "total_checkins": total_checkins,
        "freeze_count": streak.freeze_count,
        "freeze_used": streak.freeze_used or 0,
        "days_remaining": days_remaining,
        "completion_pct": completion_pct,
        "today_checked": effective_today in dates_set,
        "history": history,
        "created_at": streak.created_at.isoformat(),
    }


# ── Schemas ────────────────────────────────────────────────────────────────────


class StreakCreate(BaseModel):
    # extra="forbid" turns mass-assignment attempts (e.g. best_streak,
    # total_checkins, freeze_used — server-computed fields) into a loud 422
    # instead of a silent no-op (#1321).
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    emoji: str = Field(default="🔥", max_length=32)
    icon: str = Field(default="", max_length=100)
    description: str = Field(default="", max_length=2000)
    color: str = Field(default="", max_length=50)
    theme: str = Field(default="solid", max_length=50)
    category: str = Field(default="general", max_length=50)
    start_date: date | None = None
    target_date: date | None = None
    offset: int = Field(default=0, ge=0, le=MAX_OFFSET_DAYS)
    frequency: str = "daily"
    frequency_days: int = Field(default=1, ge=1, le=MAX_FREQUENCY_DAYS)
    snowball_mode: bool = False
    freeze_count: int = Field(default=0, ge=0, le=MAX_FREEZE_COUNT)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        return _require_nonblank_name(v)

    @field_validator("frequency")
    @classmethod
    def frequency_allowed(cls, v: str) -> str:
        return _normalize_frequency(v)

    @field_validator("start_date")
    @classmethod
    def start_date_in_window(cls, v: date | None) -> date | None:
        return _validate_date_window(v, max_future_days=MAX_START_DATE_FUTURE_DAYS, field="start_date")


class StreakUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    emoji: str | None = Field(default=None, max_length=32)
    icon: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    color: str | None = Field(default=None, max_length=50)
    theme: str | None = Field(default=None, max_length=50)
    category: str | None = Field(default=None, max_length=50)
    # start_date and offset are accepted (the edit form always re-sends them)
    # but intentionally NOT applied — they are create-only fields. They are
    # left unvalidated so editing a legacy streak whose stored start_date
    # predates the validation window doesn't 422.
    start_date: date | None = None
    offset: int | None = None
    target_date: date | None = None
    frequency: str | None = None
    frequency_days: int | None = Field(default=None, ge=1, le=MAX_FREQUENCY_DAYS)
    snowball_mode: bool | None = None
    is_archived: bool | None = None
    freeze_count: int | None = Field(default=None, ge=0, le=MAX_FREEZE_COUNT)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str | None) -> str | None:
        return _require_nonblank_name(v)

    @field_validator("frequency")
    @classmethod
    def frequency_allowed(cls, v: str | None) -> str | None:
        return _normalize_frequency(v)


class CheckInData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str = Field(default="", max_length=500)
    mood: int | None = Field(default=None, ge=1, le=5)
    check_date: date | None = None

    @field_validator("check_date")
    @classmethod
    def check_date_in_window(cls, v: date | None) -> date | None:
        return _validate_date_window(v, max_future_days=MAX_CHECKIN_FUTURE_DAYS, field="check_date")


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
    today = get_local_today()
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
    include_history: bool = Query(True),
    days_history: int = Query(365, ge=1, le=730),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    response: Response = None,
):
    q = db.query(PersonalStreak).options(selectinload(PersonalStreak.checkins))
    if not include_archived:
        q = q.filter(PersonalStreak.is_archived == False)  # noqa: E712 -- SQLAlchemy column comparison; `not` would produce wrong SQL
    if category and category != "all":
        q = q.filter(PersonalStreak.category == category)
    total = q.count()
    streaks = q.order_by(PersonalStreak.created_at).offset(offset).limit(limit).all()
    add_pagination_headers(response, total=total, limit=limit, offset=offset)
    return [_streak_to_dict(s, days_history=days_history if include_history else 0) for s in streaks]


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
        start_date=data.start_date or get_local_today(),
        target_date=data.target_date,
        offset=data.offset,
        frequency=data.frequency,
        frequency_days=max(1, data.frequency_days),
        snowball_mode=data.snowball_mode,
        freeze_count=data.freeze_count,
    )
    db.add(streak)
    db.commit()
    db.refresh(streak)

    # Automatically backfill if start_date is in the past
    if streak.start_date and streak.start_date < get_local_today():
        backfill_streak_history(db, streak)

    return _streak_to_dict(streak)


@router.put("/{streak_id}")
def update_streak(streak_id: int, data: StreakUpdate, db: Session = Depends(get_db)):
    streak = db.query(PersonalStreak).filter(PersonalStreak.id == streak_id).first()
    if not streak:
        raise HTTPException(status_code=404, detail="Streak not found")

    updatable = [
        "name",
        "emoji",
        "icon",
        "description",
        "color",
        "theme",
        "category",
        "target_date",
        "frequency",
        "frequency_days",
        "snowball_mode",
        "is_archived",
        "freeze_count",
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

    # Backfill legacy streaks whose stored start_date is already in the past
    # (start_date itself is create-only and cannot be moved on update). The
    # service caps each backfill at MAX_BACKFILL_DAYS (#1321).
    if streak.start_date and streak.start_date < get_local_today():
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

    today = data.check_date or get_local_today()
    existing = (
        db.query(StreakCheckIn)
        .filter(
            StreakCheckIn.streak_id == streak_id,
            StreakCheckIn.check_date == today,
        )
        .first()
    )

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

    today = get_local_today()
    ci = (
        db.query(StreakCheckIn)
        .filter(
            StreakCheckIn.streak_id == streak_id,
            StreakCheckIn.check_date == today,
        )
        .first()
    )

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
    today = get_local_today()
    already = (
        db.query(StreakCheckIn)
        .filter(
            StreakCheckIn.streak_id == streak_id,
            StreakCheckIn.check_date == today,
        )
        .first()
    )

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

    today = get_local_today()
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
