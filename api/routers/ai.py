from datetime import date, datetime, time, timedelta
from typing import cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from config import settings
from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from middleware.correlation_id import get_correlation_id
from models.calendar_task import CalendarTask
from models.gamification import UserStats
from models.goal import Goal, GoalState
from models.google_calendar_event import GoogleCalendarEvent
from models.note import Note, NoteTag, Tag
from pydantic import BaseModel
from services.auth_service import get_current_user
from services.http_client import http_client
from services.timezone_utils import get_local_today, get_user_tz, to_utc_datetime
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

router = APIRouter(prefix="/ai", tags=["ai"])


def _ai_disabled_response(endpoint: str) -> dict:
    """Standard response when AI_SERVICE_ENABLED=false.

    Returns a 200 with a clear 'disabled' status so the frontend can
    distinguish 'intentionally off' from 'service crashed'.
    """
    return {"status": "disabled", "ai_enabled": False, "endpoint": endpoint}


class ClassifyRequest(BaseModel):
    note_id: int
    content: str
    existing_tags: list[str] = []


@router.post("/classify")
async def classify(req: ClassifyRequest):
    if not settings.ai_service_enabled:
        return {**_ai_disabled_response("classify"), "note_id": req.note_id, "suggestions": []}
    async with http_client(timeout=30.0) as client:
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
    if not settings.ai_service_enabled:
        return {**_ai_disabled_response("usage"), "estimated_cost_usd": 0}
    async with http_client(timeout=10.0) as client:
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
    if not settings.ai_service_enabled:
        return {**_ai_disabled_response("cluster"), "clusters": [], "total_notes": 0}
    async with http_client(timeout=60.0) as client:
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
    if not settings.ai_service_enabled:
        return {
            **_ai_disabled_response("daily-recap"),
            "recap": "El servicio de IA está deshabilitado.",
            "suggestions": [],
        }
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

    async with http_client(timeout=60.0) as client:
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
    goals = db.query(Goal).filter(Goal.state == GoalState.ACTIVE).order_by(Goal.created_at.desc()).limit(10).all()
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

    recent_notes = db.query(Note.title).order_by(Note.created_at.desc()).limit(10).all()
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
    if not settings.ai_service_enabled:
        return {
            **_ai_disabled_response("chat"),
            "response": "El asistente de IA está deshabilitado en este modo.",
            "suggestions": [],
        }
    context = _gather_chat_context(db)

    async with http_client(timeout=60.0) as client:
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
                "response": (
                    "El asistente no está disponible en este momento. "
                    "Verifica la configuración de IA e inténtalo de nuevo."
                ),
                "suggestions": [],
            }


# ── Plan suggestions (#1237) ────────────────────────────────────────────────

# Priority order for the prompt: URGENT tasks get the earliest slots.
_PLAN_PRIORITY_RANK = {"URGENT": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
# Cap the planning window so a stray huge range cannot dump the whole
# tasks/events tables into one LLM prompt.
_PLAN_MAX_RANGE_DAYS = 62


class PlanSuggestRequest(BaseModel):
    week_start: str
    week_end: str
    timezone: str = "UTC"
    context_hint: str | None = None


def _task_duration_minutes(task: CalendarTask, day: date) -> int | None:
    """Derive a duration from start/end times when both are set (else None → 30min default)."""
    start = cast("time | None", task.start_time)
    end = cast("time | None", task.end_time)
    if start is None or end is None:
        return None
    minutes = int((datetime.combine(day, end) - datetime.combine(day, start)).total_seconds() // 60)
    return minutes if minutes > 0 else None


@router.post("/plan-suggest")
async def plan_suggest(
    req: PlanSuggestRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    """AI planning suggestions (#1237): slot open tasks around busy blocks.

    Builds the payload server-side — open calendar tasks (unscheduled NULL-date
    tasks are the main candidates, plus scheduled-in-range ones the AI may
    re-slot) and cached Google Calendar events as busy blocks — then forwards
    to the ai-service. Always answers 200; ``available: false`` + ``reason``
    when the AI side cannot produce suggestions.
    """
    if not settings.ai_service_enabled:
        return {"suggestions": [], "available": False, "reason": "disabled"}

    try:
        week_start = datetime.strptime(req.week_start, "%Y-%m-%d").date()
        week_end = datetime.strptime(req.week_end, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    if week_end < week_start:
        raise HTTPException(status_code=400, detail="week_end must be on or after week_start")
    if (week_end - week_start).days > _PLAN_MAX_RANGE_DAYS:
        raise HTTPException(status_code=400, detail=f"Planning range too large (max {_PLAN_MAX_RANGE_DAYS} days)")

    try:
        tz = ZoneInfo(req.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        tz = get_user_tz()

    open_tasks = (
        db.query(CalendarTask)
        .filter(
            CalendarTask.done.is_(False),
            or_(CalendarTask.date.is_(None), CalendarTask.date.between(week_start, week_end)),
        )
        .all()
    )
    open_tasks.sort(key=lambda t: (_PLAN_PRIORITY_RANK.get(t.priority.value, 4), t.created_at))
    anchor = week_start  # arbitrary day for time→datetime math; only the delta matters
    tasks_payload = [
        {
            "id": t.id,
            "title": t.title,
            "priority": t.priority.value,
            "duration_minutes": _task_duration_minutes(t, anchor),
        }
        for t in open_tasks
    ]

    # Busy blocks: cached Google events overlapping the window — including
    # events that started before it but spill in (end_at > range_start).
    range_start = datetime.combine(week_start, time.min, tzinfo=tz)
    range_end = datetime.combine(week_end, time.max, tzinfo=tz)
    events = (
        db.query(GoogleCalendarEvent)
        .filter(
            GoogleCalendarEvent.user_id == user_id,
            GoogleCalendarEvent.status != "cancelled",
            GoogleCalendarEvent.start_at <= range_end,
            or_(GoogleCalendarEvent.end_at.is_(None), GoogleCalendarEvent.end_at > range_start),
        )
        .order_by(GoogleCalendarEvent.start_at)
        .all()
    )

    busy_blocks = []
    for e in events:
        if e.all_day:
            # All-day rows are stored as UTC-midnight instants whose date part
            # IS the Google `date` — send a local-day block (Google's end.date
            # is exclusive, so [start_day, end_day) covers the event's days).
            start_day = e.start_at.date()
            end_day = (e.end_at or e.start_at).date()
            if end_day <= start_day:
                end_day = start_day + timedelta(days=1)
            busy_blocks.append({"start": f"{start_day.isoformat()}T00:00:00", "end": f"{end_day.isoformat()}T00:00:00"})
        else:
            busy_blocks.append({"start": e.start_at.isoformat(), "end": (e.end_at or e.start_at).isoformat()})

    payload = {
        "tasks": tasks_payload,
        "busy_blocks": busy_blocks,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "timezone": req.timezone,
        "context_hint": req.context_hint,
    }

    async with http_client(timeout=60.0) as client:
        try:
            headers = {"X-Request-ID": get_correlation_id()}
            if settings.internal_secret:
                headers["X-Internal-Secret"] = settings.internal_secret
            r = await client.post(
                f"{settings.ai_service_url}/plan-suggest",
                json=payload,
                headers=headers,
            )
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError:
            return {"suggestions": [], "available": False, "reason": "unavailable"}
