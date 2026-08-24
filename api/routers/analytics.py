"""Analytics router — unified dashboard + internal usage tracking (#251, #250).

``GET /analytics/dashboard`` aggregates the existing system stats, activity
time-series, mood stats, and AI usage into a single response so the frontend
analytics page can render everything with one round-trip. ``POST /analytics/track``
records a lightweight usage event from the frontend (only while the app is in
the foreground). ``GET /analytics/usage`` returns the aggregated usage summary.
"""

import httpx
from config import settings
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from middleware.correlation_id import get_correlation_id
from models.gamification import UserStats, XPEvent
from models.goal import Goal
from models.note import Note
from models.note import Tag as TagModel
from models.skill import Skill
from pydantic import BaseModel, field_validator
from services.auth_service import get_current_user
from services.mood_service import get_mood_history, get_mood_stats
from services.usage_service import (
    VALID_EVENT_TYPES,
    get_usage_summary,
    track_event,
)
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

router = APIRouter(prefix="/analytics", tags=["analytics"])


class TrackRequest(BaseModel):
    """Schema for a usage event sent from the frontend."""

    event_type: str
    event_data: dict | None = None

    @field_validator("event_type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        if v not in VALID_EVENT_TYPES:
            raise ValueError(
                f"event_type must be one of: {', '.join(sorted(VALID_EVENT_TYPES))}"
            )
        return v


def _system_stats(db: Session) -> dict:
    """Reuse the same queries as /stats/system (kept local to avoid a cross-router import)."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    notes_count = db.query(Note).count()
    tags_count = db.query(TagModel).count()
    goals_count = db.query(Goal).count()
    skills_count = db.query(Skill).count()

    stats = db.query(UserStats).first()
    xp_events_week = db.query(XPEvent).filter(XPEvent.created_at >= week_ago).count()

    return {
        "notes": notes_count,
        "tags": tags_count,
        "goals": goals_count,
        "skills": skills_count,
        "total_xp": stats.total_xp if stats else 0,
        "current_streak": stats.current_streak if stats else 0,
        "xp_events_week": xp_events_week,
    }


def _activity(db: Session, days: int) -> dict:
    """Daily activity time-series (notes created + XP events) for the last N days."""
    if days < 1:
        days = 1
    if days > 366:
        days = 366

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)

    notes_by_day = (
        db.query(func.date(Note.created_at).label("d"), func.count(Note.id).label("c"))
        .filter(Note.created_at >= since)
        .group_by(func.date(Note.created_at))
        .all()
    )
    xp_by_day = (
        db.query(func.date(XPEvent.created_at).label("d"), func.count(XPEvent.id).label("c"))
        .filter(XPEvent.created_at >= since)
        .group_by(func.date(XPEvent.created_at))
        .all()
    )

    notes_map = {str(r.d): r.c for r in notes_by_day}
    xp_map = {str(r.d): r.c for r in xp_by_day}

    daily = []
    for i in range(days):
        day = (now - timedelta(days=i)).date()
        day_str = day.isoformat()
        daily.append(
            {
                "date": day_str,
                "notes_created": notes_map.get(day_str, 0),
                "xp_events": xp_map.get(day_str, 0),
            }
        )
    return {"days": daily}


async def _ai_usage() -> dict:
    """Fetch monthly AI usage from the ai-service (best-effort)."""
    if not settings.ai_service_enabled:
        return {"ai_enabled": False, "estimated_cost_usd": 0, "status": "disabled"}
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            headers = {"X-Request-ID": get_correlation_id()}
            if settings.internal_secret:
                headers["X-Internal-Secret"] = settings.internal_secret
            r = await client.get(f"{settings.ai_service_url}/usage", headers=headers)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError:
            return {"ai_enabled": False, "estimated_cost_usd": 0, "error": "AI service unreachable"}


@router.get("/dashboard")
async def get_dashboard(
    days: int = Query(30, ge=1, le=366),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    """Unified analytics dashboard: system + activity + mood + AI usage + usage summary."""
    system = _system_stats(db)
    activity = _activity(db, days)
    mood_stats = get_mood_stats(db, user_id)
    mood_history = [
        {
            "entry_date": e.entry_date.isoformat(),
            "score": e.score,
        }
        for e in get_mood_history(db, user_id, days)
    ]
    ai_usage = await _ai_usage()
    usage = get_usage_summary(db, user_id, days)

    return {
        "system": system,
        "activity": activity,
        "mood": {
            "stats": mood_stats,
            "history": mood_history,
        },
        "ai_usage": ai_usage,
        "usage": usage,
    }


@router.post("/track")
def track(
    data: TrackRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    """Record a usage event from the frontend (foreground-only)."""
    event = track_event(db, user_id, data.event_type, data.event_data)
    return {"status": "ok", "id": event.id}


@router.get("/usage")
def usage(
    days: int = Query(30, ge=1, le=366),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    """Aggregated internal usage summary for the last ``days`` days."""
    return get_usage_summary(db, user_id, days)
