from datetime import datetime, timedelta

from database import get_db
from fastapi import APIRouter, Depends
from models.gamification import UserStats, XPEvent
from models.goal import Goal
from models.note import Note
from models.note import Tag as TagModel
from models.skill import Skill
from sqlalchemy.orm import Session

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/system")
def get_system_stats(db: Session = Depends(get_db)):
    """Get system-wide statistics."""
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)

    notes_count = db.query(Note).count()
    tags_count = db.query(TagModel).count()
    goals_count = db.query(Goal).count()
    skills_count = db.query(Skill).count()

    stats = db.query(UserStats).first()
    xp_events_week = db.query(XPEvent).filter(
        XPEvent.created_at >= week_ago
    ).count()

    return {
        "notes": notes_count,
        "tags": tags_count,
        "goals": goals_count,
        "skills": skills_count,
        "total_xp": stats.total_xp if stats else 0,
        "current_streak": stats.current_streak if stats else 0,
        "xp_events_week": xp_events_week,
    }


@router.get("/activity")
def get_activity_stats(
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Get activity statistics for the last N days."""
    now = datetime.utcnow()
    since = now - timedelta(days=days)

    daily_stats = []
    for i in range(days):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        notes_created = db.query(Note).filter(
            Note.created_at >= day_start,
            Note.created_at < day_end
        ).count()

        xp_events = db.query(XPEvent).filter(
            XPEvent.created_at >= day_start,
            XPEvent.created_at < day_end
        ).count()

        daily_stats.append({
            "date": day_start.date().isoformat(),
            "notes_created": notes_created,
            "xp_events": xp_events,
        })

    return {"days": daily_stats}
