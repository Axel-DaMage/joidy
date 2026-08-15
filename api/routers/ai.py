import httpx
from config import settings
from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from middleware.correlation_id import get_correlation_id
from models.goal import Goal, GoalState
from models.gamification import UserStats
from models.note import Note, NoteTag, Tag
from pydantic import BaseModel
from services.auth_service import get_current_user
from services.timezone_utils import get_local_today, to_utc_datetime
from sqlalchemy import func
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
        target_date = get_local_today().isoformat()

    try:
        day = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")

    # Query the DB using UTC boundaries that correspond to the user-local day,
    # since created_at/updated_at/completed_at are stored as UTC timestamps.
    start = to_utc_datetime(day)
    end = to_utc_datetime(day + timedelta(days=1))

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


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


def _gather_chat_context(db: Session) -> dict:
    """Collect personal context (goals, streaks/XP, top tags, recent notes)
    to send to the ai-service /chat endpoint.

    Kept lightweight: only titles/counts are sent, never full note content,
    to limit PII exposure and token usage.
    """
    goals = (
        db.query(Goal)
        .filter(Goal.state == GoalState.ACTIVE)
        .order_by(Goal.created_at.desc())
        .limit(10)
        .all()
    )
    goal_ctx = [
        {
            "title": g.title,
            "state": g.state.value,
            "target_value": g.target_value,
            "current_value": 0,
            "progress_pct": 0,
        }
        for g in goals
    ]

    stats = db.query(UserStats).filter(UserStats.id == 1).first()
    xp = stats.total_xp if stats else None
    streaks_ctx: list[dict] = []
    if stats and stats.current_streak:
        streaks_ctx = [{"name": "Actividad diaria", "current_streak": stats.current_streak}]

    top_tags = (
        db.query(Tag.name, func.count(NoteTag.tag_id).label("n"))
        .join(NoteTag, NoteTag.tag_id == Tag.id)
        .group_by(Tag.id)
        .order_by(func.count(NoteTag.tag_id).desc())
        .limit(5)
        .all()
    )
    top_tag_names = [t[0] for t in top_tags]

    recent_notes = (
        db.query(Note.title)
        .order_by(Note.created_at.desc())
        .limit(10)
        .all()
    )
    recent_note_titles = [n[0] for n in recent_notes if n[0]]

    return {
        "goals": goal_ctx,
        "streaks": streaks_ctx,
        "xp": xp,
        "top_tags": top_tag_names,
        "recent_notes": recent_note_titles,
    }


@router.post("/chat")
async def chat(
    req: ChatRequest,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Conversational AI assistant endpoint.

    Fetches the user's personal context (goals, streaks, XP, top tags, recent
    note titles) and forwards the conversation + context to the ai-service
    /chat endpoint. The response is returned without persisting chat history
    on the backend (history lives in the frontend sessionStorage).
    """
    context = _gather_chat_context(db)

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            headers = {"X-Request-ID": get_correlation_id()}
            if settings.internal_secret:
                headers["X-Internal-Secret"] = settings.internal_secret
            r = await client.post(
                f"{settings.ai_service_url}/chat",
                json={"messages": [m.model_dump() for m in req.messages], "context": context},
                headers=headers,
            )
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError:
            return {
                "status": "unavailable",
                "response": "El asistente no está disponible en este momento. Verifica la configuración de IA e inténtalo de nuevo.",
                "suggestions": [],
            }
