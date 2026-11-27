"""System/activity stats aggregation shared by routers (#1532).

``routers/stats.py`` (``/stats/system``, ``/stats/activity``) and
``routers/analytics.py`` (``/analytics/dashboard``) need the same queries —
they used to carry verbatim copies that could drift apart.
"""

from datetime import UTC, datetime, timedelta

from models.gamification import UserStats, XPEvent
from models.goal import Goal
from models.note import Note
from models.note import Tag as TagModel
from models.skill import Skill
from sqlalchemy import func
from sqlalchemy.orm import Session


def get_system_stats(db: Session) -> dict:
    """System-wide counts plus XP/streak summary for the singleton user."""
    now = datetime.now(UTC)
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


def get_activity_stats(db: Session, days: int) -> dict:
    """Daily activity time-series (notes created + XP events) for the last N days."""
    if days < 1:
        days = 1
    if days > 366:
        days = 366

    now = datetime.now(UTC)
    since = now - timedelta(days=days)

    # Single grouped query per table instead of N individual queries.
    notes_by_day = (
        db.query(
            func.date(Note.created_at).label("d"),
            func.count(Note.id).label("c"),
        )
        .filter(Note.created_at >= since)
        .group_by(func.date(Note.created_at))
        .all()
    )
    xp_by_day = (
        db.query(
            func.date(XPEvent.created_at).label("d"),
            func.count(XPEvent.id).label("c"),
        )
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
