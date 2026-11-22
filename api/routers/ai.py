import json
import logging
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from config import settings
from database import SessionLocal, get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from middleware.correlation_id import get_correlation_id
from models.calendar_task import CalendarTask
from models.chat_session import ChatSession
from models.gamification import UserStats
from models.goal import Goal, GoalState
from models.google_calendar_event import GoogleCalendarEvent
from models.note import Note, NoteTag, Tag
from pydantic import BaseModel, Field
from services.auth_service import get_current_user
from services.http_client import http_client
from services.timezone_utils import get_local_today, get_user_tz, to_utc_datetime
from services.usage_service import EVENT_FEATURE_USE, track_event
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


def _ai_disabled_response(endpoint: str) -> dict:
    """Standard response when AI_SERVICE_ENABLED=false.

    Returns a 200 with a clear 'disabled' status so the frontend can
    distinguish 'intentionally off' from 'service crashed'.
    """
    return {"status": "disabled", "ai_enabled": False, "endpoint": endpoint}


class ClassifyRequest(BaseModel):
    note_id: int
    content: str = Field(max_length=10_000)
    existing_tags: list[Annotated[str, Field(max_length=100)]] = Field(default_factory=list, max_length=100)


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


def _derive_ai_status(health: dict) -> tuple[str, str | None]:
    """Map the ai-service /health body to the /ai/usage ``ai_status`` contract (#1460).

    - ``disabled``    — AI not configured (no provider keys at ai-service).
    - ``unavailable`` — no LLM provider reachable.
    - ``degraded``    — usable but impaired: primary LLM down and a fallback
      is serving, or the embedding provider is unreachable (RAG degraded).
    - ``ok``          — configured providers healthy.
    """
    if not health.get("ai_enabled"):
        return "disabled", "No AI provider configured"
    status = health.get("status")
    if status == "ok":
        return "ok", None

    # Compose a human-readable detail from the privileged reachability probe
    # when present (requires INTERNAL_SECRET; otherwise fall back to a
    # generic explanation).
    reach = health.get("reachability") or {}
    llm = reach.get("llm") or {}
    emb = reach.get("embedding") or {}
    parts: list[str] = []
    if llm.get("configured") and not llm.get("primary_ok") and llm.get("active"):
        parts.append(f"primary LLM provider unreachable — '{llm['active']}' fallback active")
    if emb.get("configured") and not emb.get("available"):
        parts.append("embedding provider unreachable (RAG degraded)")
    elif emb.get("configured") and not emb.get("primary_ok"):
        parts.append("embedding fallback active")

    if status == "degraded":
        return "degraded", "; ".join(parts) or "One or more configured providers are unreachable"
    # "unavailable" or anything unexpected → cannot serve chat at all.
    return "unavailable", "; ".join(parts) or "No reachable LLM provider"


@router.get("/usage")
async def usage():
    if not settings.ai_service_enabled:
        return {
            **_ai_disabled_response("usage"),
            "estimated_cost_usd": 0,
            "ai_status": "disabled",
            "ai_status_detail": "AI service disabled (AI_SERVICE_ENABLED=false)",
        }
    async with http_client(timeout=10.0) as client:
        headers = {"X-Request-ID": get_correlation_id()}
        if settings.internal_secret:
            headers["X-Internal-Secret"] = settings.internal_secret
        try:
            r = await client.get(f"{settings.ai_service_url}/usage", headers=headers)
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPError as exc:
            return {
                "ai_enabled": False,
                "estimated_cost_usd": 0,
                "error": "AI service unreachable",
                "ai_status": "unavailable",
                "ai_status_detail": f"ai-service unreachable ({type(exc).__name__})",
            }
        # Probe /health (real provider reachability, #1460) to derive the
        # ai_status contract consumed by the frontend.
        try:
            hr = await client.get(f"{settings.ai_service_url}/health", headers=headers)
            hr.raise_for_status()
            ai_status, ai_status_detail = _derive_ai_status(hr.json())
        except httpx.HTTPError as exc:
            ai_status, ai_status_detail = "unavailable", f"ai-service /health unreachable ({type(exc).__name__})"
        data["ai_status"] = ai_status
        data["ai_status_detail"] = ai_status_detail
        return data


@router.post("/cluster")
async def cluster_notes(
    eps: float = Query(default=0.3, gt=0.0, le=2.0),
    min_samples: int = Query(default=3, ge=1, le=200),
    max_notes: int = Query(default=500, ge=1, le=2_000),
):
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
    role: str = Field(max_length=20)
    content: str = Field(max_length=20_000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=50)
    session_id: int | None = None


# ── Chat session persistence (#1131) ────────────────────────────────────────


def _latest_session(db: Session, user_id: int) -> ChatSession | None:
    return (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
        .first()
    )


def _get_or_create_session(db: Session, user_id: int, session_id: int | None) -> ChatSession:
    """Return the session to append to: the requested one if it belongs to the
    user, otherwise the most recent one, creating a fresh row when none exists.
    """
    session: ChatSession | None = None
    if session_id is not None:
        session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == user_id).first()
    if session is None:
        session = _latest_session(db, user_id)
    if session is None:
        session = ChatSession(user_id=user_id, messages=[])
        db.add(session)
        db.flush()
    return session


# Content + JSON marker for the synthetic assistant reply persisted when the
# AI exchange fails upstream (#1460): the user turn no longer dangles in the
# session, and the UI can render the ``error`` flag as a failed reply instead
# of a normal assistant bubble.
_CHAT_ERROR_MESSAGE = "El asistente no está disponible en este momento. Inténtalo de nuevo en unos minutos."


def _append_message(
    db: Session,
    session: ChatSession,
    role: str,
    content: str,
    extra: dict | None = None,
) -> None:
    """Append a turn to the session, skipping exact duplicates of the last
    stored turn so client retries cannot write the same message twice.
    Assigns a fresh list so SQLAlchemy detects the JSON mutation.

    ``extra`` keys are merged into the stored message dict — used for the
    ``error`` marker on failed exchanges (#1460) without a schema change.
    """
    msgs: list[dict] = list(session.messages or [])
    if msgs and msgs[-1].get("role") == role and msgs[-1].get("content") == content:
        return
    msg: dict = {"role": role, "content": content, "ts": int(datetime.now(UTC).timestamp() * 1000)}
    if extra:
        msg.update(extra)
    msgs.append(msg)
    if session.title is None and role == "user":
        session.title = content[:80]
    session.messages = msgs
    db.flush()


def _record_chat_usage(db: Session, user_id: int, session_id: int) -> None:
    """Track one ``feature_use`` usage event per answered chat turn (#1131 AC4)."""
    try:
        track_event(db, user_id, EVENT_FEATURE_USE, {"feature": "ai_chat", "session_id": session_id})
    except Exception:
        logger.warning("Failed to record ai_chat usage event", exc_info=True)


def _persist_assistant_reply(
    db: Session,
    session_id: int,
    user_id: int,
    answer: str,
    extra: dict | None = None,
) -> bool:
    """Append the assistant reply to the session and record usage (#1131).

    Returns False on any failure so callers can retry on a fresh connection.
    """
    try:
        sess = db.get(ChatSession, session_id)
        if sess is None:
            return False
        _append_message(db, sess, "assistant", answer, extra=extra)
        db.commit()
        _record_chat_usage(db, user_id, session_id)
        return True
    except Exception:
        logger.debug("Assistant reply persist failed on this session", exc_info=True)
        return False


def _persist_stream_reply(
    db: Session,
    session_id: int,
    user_id: int,
    content: str,
    extra: dict | None = None,
) -> None:
    """Persist a streamed reply, falling back to a fresh connection.

    Try the request-scoped ``db`` first — yield-dependencies stay open until
    the StreamingResponse finishes on supported FastAPI versions — then a
    fresh ``SessionLocal`` when it is already closed.
    """
    if _persist_assistant_reply(db, session_id, user_id, content, extra=extra):
        return
    try:
        with SessionLocal() as persist_db:
            _persist_assistant_reply(persist_db, session_id, user_id, content, extra=extra)
    except Exception:
        logger.warning("Failed to persist streamed chat reply", exc_info=True)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


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


def _validate_chat_messages(req: ChatRequest) -> None:
    if not req.messages:
        raise HTTPException(status_code=422, detail="messages must not be empty")
    if req.messages[-1].role != "user":
        raise HTTPException(status_code=422, detail="last message must be from user")


def _internal_headers() -> dict[str, str]:
    headers = {"X-Request-ID": get_correlation_id()}
    if settings.internal_secret:
        headers["X-Internal-Secret"] = settings.internal_secret
    return headers


def _upstream_error_detail(exc: BaseException) -> str | None:
    """Extract the ``detail`` field from an upstream JSON error body (#1460).

    ``httpx.HTTPStatusError`` carries the response — ai-service 500s now
    include provider + error class in ``detail``, so forwarding it makes the
    failure diagnosable end-to-end.
    """
    resp = getattr(exc, "response", None)
    if resp is None:
        return None
    try:
        detail = resp.json().get("detail")
        return str(detail) if detail else None
    except Exception:
        return None


async def _read_upstream_detail(r) -> str | None:
    """Best-effort read of a non-200 streaming response body for the SSE
    error frame (#1460)."""
    try:
        raw = await r.aread()
    except Exception:
        return None
    try:
        detail = json.loads(raw).get("detail")
        return str(detail) if detail else None
    except Exception:
        return None


@router.post("/chat")
async def chat(
    req: ChatRequest,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Conversational AI assistant endpoint (#1131).

    Fetches the user's personal context (goals, streaks, XP, top tags, recent
    note titles) and forwards the conversation + context to the ai-service
    /chat endpoint, which grounds the answer in the user's notes via RAG.
    The exchange is persisted in ``chat_sessions`` and tracked in
    ``usage_events``.
    """
    if not settings.ai_service_enabled:
        return {
            **_ai_disabled_response("chat"),
            "response": "El asistente de IA está deshabilitado en este modo.",
            "suggestions": [],
        }
    _validate_chat_messages(req)

    session = _get_or_create_session(db, user_id, req.session_id)
    _append_message(db, session, "user", req.messages[-1].content)
    db.commit()

    context = _gather_chat_context(db)

    async with http_client(timeout=60.0) as client:
        try:
            r = await client.post(
                f"{settings.ai_service_url}/chat",
                json={
                    "messages": [m.model_dump() for m in req.messages],
                    "context": context,
                },
                headers=_internal_headers(),
            )
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPError as exc:
            # #1460: persist an error-marked assistant reply so the user turn
            # doesn't dangle — history visibly shows the exchange failed.
            upstream_detail = _upstream_error_detail(exc)
            logger.warning("ai-service /chat request failed: %s (upstream detail: %s)", exc, upstream_detail)
            _append_message(
                db,
                session,
                "assistant",
                _CHAT_ERROR_MESSAGE,
                extra={"error": True, "status": "unavailable"},
            )
            db.commit()
            return {
                "status": "unavailable",
                "response": (
                    "El asistente no está disponible en este momento. "
                    "Verifica la configuración de IA e inténtalo de nuevo."
                ),
                "error": upstream_detail or type(exc).__name__,
                "suggestions": [],
                "session_id": session.id,
            }

    answer = data.get("response") or ""
    if data.get("status") == "success" and answer:
        _append_message(db, session, "assistant", answer)
        db.commit()
        _record_chat_usage(db, user_id, session.id)
    else:
        # Non-success upstream statuses (disabled / circuit_open / provider
        # error surfaced as 200-with-status) get an error-marked assistant
        # turn too — same no-dangling-user-message rule (#1460).
        _append_message(
            db,
            session,
            "assistant",
            answer or _CHAT_ERROR_MESSAGE,
            extra={"error": True, "status": data.get("status") or "error"},
        )
        db.commit()
    return {**data, "session_id": session.id}


@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Streaming variant of /chat (#1131): proxies the ai-service SSE stream.

    Emits an ``event: session`` frame first so the client learns the
    ``session_id``, then forwards upstream ``meta``/``token``/``done``/``error``
    frames verbatim. The accumulated assistant reply is persisted in
    ``chat_sessions`` once the stream completes.
    """
    if not settings.ai_service_enabled:
        return {
            **_ai_disabled_response("chat"),
            "response": "El asistente de IA está deshabilitado en este modo.",
            "suggestions": [],
        }
    _validate_chat_messages(req)

    session = _get_or_create_session(db, user_id, req.session_id)
    _append_message(db, session, "user", req.messages[-1].content)
    db.commit()
    session_id = session.id

    context = _gather_chat_context(db)
    payload = {
        "messages": [m.model_dump() for m in req.messages],
        "context": context,
        "stream": True,
    }
    headers = _internal_headers()

    async def event_stream():
        yield _sse("session", {"session_id": session_id})
        tokens: list[str] = []
        last_event = ""
        failed = False
        try:
            async with http_client(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{settings.ai_service_url}/chat",
                    json=payload,
                    headers=headers,
                ) as r:
                    if r.status_code != 200:
                        failed = True
                        # Structured error frame (#1460): forward the upstream
                        # error detail (provider/error class) when present so
                        # the UI and logs can diagnose the failure.
                        yield _sse(
                            "error",
                            {
                                "message": "El servicio de IA no está disponible.",
                                "status": "unavailable",
                                "error_class": f"HTTP {r.status_code}",
                                "detail": await _read_upstream_detail(r),
                            },
                        )
                    else:
                        async for line in r.aiter_lines():
                            # Forward upstream SSE verbatim; track token frames
                            # to reconstruct the full assistant reply for
                            # persistence, and error frames so a failed exchange
                            # still gets an error-marked assistant turn (#1460).
                            if line.startswith("event:"):
                                last_event = line[6:].strip()
                            elif line.startswith("data:") and last_event == "token":
                                try:
                                    tokens.append(json.loads(line[5:].strip()).get("text", ""))
                                except (json.JSONDecodeError, AttributeError):
                                    pass
                            elif line.startswith("data:") and last_event == "error":
                                failed = True
                            elif line == "":
                                # Blank line = end of the current SSE event block.
                                last_event = ""
                            yield line + "\n"
        except httpx.HTTPError as exc:
            failed = True
            logger.warning("ai-service /chat stream request failed: %s", exc)
            yield _sse(
                "error",
                {
                    "message": "El asistente no está disponible en este momento.",
                    "status": "unavailable",
                    "error_class": type(exc).__name__,
                    "detail": _upstream_error_detail(exc),
                },
            )

        answer = "".join(tokens).strip()
        if answer:
            _persist_stream_reply(db, session_id, user_id, answer)
        elif failed:
            # No assistant tokens were produced — persist an error-marked
            # reply so the user turn doesn't dangle (#1460).
            _persist_stream_reply(
                db,
                session_id,
                user_id,
                _CHAT_ERROR_MESSAGE,
                extra={"error": True, "status": "unavailable"},
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Session-Id": str(session_id),
        },
    )


@router.get("/chat/history")
def chat_history(
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the user's most recent chat session so the UI can restore the
    conversation across reloads (#1131 AC2)."""
    session = _latest_session(db, user_id)
    if session is None:
        return {"session_id": None, "messages": []}
    return {"session_id": session.id, "messages": session.messages or []}


@router.delete("/chat/history")
def clear_chat_history(
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete all of the user's chat sessions (the UI "clear conversation" action)."""
    db.query(ChatSession).filter(ChatSession.user_id == user_id).delete()
    db.commit()
    return {"status": "cleared"}


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


def _aware_utc(dt: datetime) -> datetime:
    """Return ``dt`` tz-aware in UTC.

    ``DateTime(timezone=True)`` columns come back naive on SQLite (the test
    engine); values are stored as UTC instants, so reattaching UTC is safe.
    """
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


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
            busy_blocks.append(
                {"start": _aware_utc(e.start_at).isoformat(), "end": _aware_utc(e.end_at or e.start_at).isoformat()}
            )

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
