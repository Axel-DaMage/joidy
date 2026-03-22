from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.gamification import StreakRecord, UserStats, XPEvent
from services.gamification_engine import PLANT_STAGES, process_event



router = APIRouter(prefix="/gamification", tags=["gamification"])


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    stats = db.query(UserStats).filter(UserStats.id == 1).first()
    if not stats:
        # Auto-create on first access
        stats = UserStats(id=1)
        db.add(stats)
        db.commit()
        db.refresh(stats)

    stage_name = PLANT_STAGES[stats.plant_stage][1] if stats.plant_stage < len(PLANT_STAGES) else "tree"
    next_stage_xp = PLANT_STAGES[stats.plant_stage + 1][0] if stats.plant_stage + 1 < len(PLANT_STAGES) else None

    return {
        "total_xp": stats.total_xp,
        "current_streak": stats.current_streak,
        "longest_streak": stats.longest_streak,
        "plant_stage": stats.plant_stage,
        "plant_stage_name": stage_name,
        "next_stage_xp": next_stage_xp,
        "xp_to_next_stage": (next_stage_xp - stats.total_xp) if next_stage_xp else None,
        "last_activity_date": stats.last_activity_date.isoformat() if stats.last_activity_date else None,
    }


@router.get("/streak-history")
def get_streak_history(days: int = 30, db: Session = Depends(get_db)):
    records = (
        db.query(StreakRecord)
        .order_by(StreakRecord.activity_date.desc())
        .limit(days)
        .all()
    )
    return [
        {"date": r.activity_date.isoformat(), "xp": r.xp_earned}
        for r in records
    ]


@router.get("/recent-events")
def get_recent_events(limit: int = 20, db: Session = Depends(get_db)):
    events = (
        db.query(XPEvent)
        .order_by(XPEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "type": e.event_type,
            "xp": e.xp,
            "at": e.created_at.isoformat(),
        }
        for e in events
    ]


@router.post("/ping")
def ping_activity(db: Session = Depends(get_db)):
    """Called when user opens the app — awards daily XP if not already done today."""
    gami = process_event(db, "daily_activity")
    # Reload full stats so the response includes next_stage_xp, xp_to_next_stage, etc.
    stats = db.query(UserStats).filter_by(id=1).first()
    next_stage_xp = PLANT_STAGES[gami.plant_stage + 1][0] if gami.plant_stage + 1 < len(PLANT_STAGES) else None
    return {
        **vars(gami),
        "longest_streak": stats.longest_streak if stats else 0,
        "next_stage_xp": next_stage_xp,
        "xp_to_next_stage": (next_stage_xp - gami.total_xp) if next_stage_xp else None,
        "last_activity_date": stats.last_activity_date.isoformat() if stats and stats.last_activity_date else None,
    }
