import httpx
from config import settings
from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from middleware.correlation_id import get_correlation_id
from models.note import Note
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta, timezone

router = APIRouter(prefix="/ai", tags=["ai"])

class ClassifyRequest(BaseModel):
    note_id: int
    content: str
    existing_tags: list[str] = []

@router.post("/classify")
async def classify(req: ClassifyRequest):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            headers = {"X-Request-ID": get_correlation_id()}
            if settings.internal_secret:
                headers["X-Internal-Secret"] = settings.internal_secret
            r = await client.post(
                f"{settings.ai_service_url}/classify",
                json=req.model_dump(),
                headers=headers,
            )
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError:
            # AI classification is an optional enhancement — return a graceful
            # degraded response instead of 502 so the note save flow is not
            # disrupted and the user sees no error toast (#261).
            return {"status": "unavailable", "note_id": req.note_id, "suggestions": []}

@router.get("/usage")
async def usage():
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            headers = {"X-Request-ID": get_correlation_id()}
            if settings.internal_secret:
                headers["X-Internal-Secret"] = settings.internal_secret
            r = await client.get(f"{settings.ai_service_url}/usage", headers=headers)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError:
            return {"ai_enabled": False, "estimated_cost_usd": 0, "error": "AI service unreachable"}


@router.post("/cluster")
async def cluster_notes(eps: float = 0.3, min_samples: int = 3, max_notes: int = 500):
    """Cluster notes by semantic similarity via the ai-service (#393)."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            headers = {"X-Request-ID": get_correlation_id()}
            if settings.internal_secret:
                headers["X-Internal-Secret"] = settings.internal_secret
            r = await client.post(
                f"{settings.ai_service_url}/cluster",
                params={"eps": eps, "min_samples": min_samples, "max_notes": max_notes},
                headers=headers,
            )
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError:
            return {"clusters": [], "total_notes": 0, "error": "AI service unreachable"}


@router.post("/daily-recap")
async def daily_recap(
    target_date: str | None = None,
    db: Session = Depends(get_db),
):
    """Generate an AI daily recap from the day's activity (#354).

    Gathers notes created, XP gained, goals completed, and focus time,
    then asks the ai-service to generate a natural-language summary.
    """
    if target_date is None:
        target_date = date.today().isoformat()

    try:
        day = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")

    start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    # Gather the day's activity from the DB
    notes_created = db.query(Note).filter(Note.created_at >= start, Note.created_at < end).all()
    notes_edited = db.query(Note).filter(Note.updated_at >= start, Note.updated_at < end, Note.created_at < start).all()

    # XP and goals — query gamification events and goals
    from models.goal import Goal
    goals_completed = db.query(Goal).filter(Goal.completed_at >= start, Goal.completed_at < end).count()

    note_titles = [n.title for n in notes_created[:10]]

    payload = {
        "date": target_date,
        "notes_created": len(notes_created),
        "notes_edited": len(notes_edited),
        "xp_gained": 0,  # XP events not tracked per-day in the current schema
        "streak_maintained": len(notes_created) > 0,
        "goals_completed": goals_completed,
        "focus_time_minutes": 0,  # Pomodoro time not persisted server-side yet
        "note_titles": note_titles,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            headers = {"X-Request-ID": get_correlation_id()}
            if settings.internal_secret:
                headers["X-Internal-Secret"] = settings.internal_secret
            r = await client.post(
                f"{settings.ai_service_url}/daily-recap",
                json=payload,
                headers=headers,
            )
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError:
            return {
                "status": "unavailable",
                "recap": "No se pudo generar el resumen diario. El servicio de IA no está disponible.",
                "suggestions": [],
            }
