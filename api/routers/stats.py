from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from services import stats_service
from sqlalchemy.orm import Session

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/system")
def get_system_stats(db: Session = Depends(get_db)):
    """Get system-wide statistics."""
    return stats_service.get_system_stats(db)


@router.get("/activity")
def get_activity_stats(days: int = 30, db: Session = Depends(get_db)):
    """Get activity statistics for the last N days."""
    if days < 1:
        raise HTTPException(status_code=400, detail="days must be >= 1")
    return stats_service.get_activity_stats(db, days)
