from database import get_db
from fastapi import APIRouter, BackgroundTasks, Depends
from models.gamification import StreakRecord, UserStats, XPEvent
from services.gamification_engine import PLANT_STAGES, process_event
from services.response_cache import clear_api_caches, register_cache_clearer, ttl_cache
from sqlalchemy.orm import Session

router = APIRouter(prefix="/gamification", tags=["gamification"])




@ttl_cache(ignore_params={"db"})
def _cached_stats(db: Session):
    stats = db.query(UserStats).filter(UserStats.id == 1).first()
    if not stats:
        # Auto-create on first access
        stats = UserStats(id=1)
        db.add(stats)
        db.commit()
        db.refresh(stats)

    stage_name = PLANT_STAGES[stats.plant_stage][1] if stats.plant_stage < len(PLANT_STAGES) else PLANT_STAGES[-1][1]
    next_stage_xp = PLANT_STAGES[stats.plant_stage + 1][0] if stats.plant_stage + 1 < len(PLANT_STAGES) else None

    # Heal: active today but streak still at 0 (written by old buggy engine)
    from datetime import date as _date
    if stats.current_streak == 0 and stats.last_activity_date == _date.today():
        stats.current_streak = 1
        if stats.longest_streak < 1:
            stats.longest_streak = 1
        db.commit()
        db.refresh(stats)

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


register_cache_clearer(_cached_stats.cache_clear)  # type: ignore[attr-defined]


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    return _cached_stats(db)


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


@ttl_cache(ignore_params={"db"})
def _cached_recent_events(limit: int = 20, db: Session = Depends(get_db)):
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


def get_recent_events(limit: int = 20, db: Session = Depends(get_db)):
    return _cached_recent_events(limit=limit, db=db)


register_cache_clearer(_cached_recent_events.cache_clear)  # type: ignore[attr-defined]


@router.get("/recent-events")
def get_recent_events_route(limit: int = 20, db: Session = Depends(get_db)):
    return get_recent_events(limit=limit, db=db)


@router.post("/ping")
def ping_activity(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Called when user opens the app — awards daily XP if not already done today."""
    gami = process_event(db, "daily_activity")
    clear_api_caches()

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
