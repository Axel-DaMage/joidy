"""Endpoints for triggering _joidy/ vault file writes."""

from datetime import date

from database import get_db
from fastapi import APIRouter, Depends
from services.joidy_vault_writer import write_daily, write_objectives, write_skills
from sqlalchemy.orm import Session

router = APIRouter(prefix="/vault", tags=["vault"])


@router.post("/write-daily")
def trigger_write_daily(db: Session = Depends(get_db)):
    ok = write_daily(db)
    return {"status": "ok" if ok else "no_vault", "file": f"_joidy/daily/{date.today().isoformat()}.md"}


@router.post("/write-objectives")
def trigger_write_objectives(db: Session = Depends(get_db)):
    ok = write_objectives(db)
    return {"status": "ok" if ok else "no_vault"}


@router.post("/write-skills")
def trigger_write_skills(db: Session = Depends(get_db)):
    ok = write_skills(db)
    return {"status": "ok" if ok else "no_vault"}
