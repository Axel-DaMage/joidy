"""Endpoints for triggering _joidy/ vault file writes."""

from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from services.joidy_vault_writer import restore_goals_from_vault, write_daily, write_objectives, write_skills
from services.timezone_utils import get_local_today
from sqlalchemy.orm import Session

router = APIRouter(prefix="/vault", tags=["vault"])


@router.post("/write-daily")
def trigger_write_daily(db: Session = Depends(get_db)):
    ok = write_daily(db)
    return {"status": "ok" if ok else "no_vault", "file": f"_joidy/daily/{get_local_today().isoformat()}.md"}


@router.post("/write-objectives")
def trigger_write_objectives(db: Session = Depends(get_db)):
    ok = write_objectives(db)
    return {"status": "ok" if ok else "no_vault"}


@router.post("/write-skills")
def trigger_write_skills(db: Session = Depends(get_db)):
    ok = write_skills(db)
    return {"status": "ok" if ok else "no_vault"}


@router.post("/restore-goals")
def trigger_restore_goals(db: Session = Depends(get_db)):
    """Restore goals from joidy_managed files in Objetivos/ (#504)."""
    try:
        return restore_goals_from_vault(db)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Vault not ready: {e}")
