import logging
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter

from config import settings
from database import init_db
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from logging_config import setup_logging
from middleware.metrics import MetricsMiddleware
from middleware.rate_limit import RateLimitMiddleware
from middleware.request_id import RequestIdMiddleware
from routers import (
    folders,
    ai,
    auth,
    config,
    export,
    gamification,
    goals,
    metrics,
    notes,
    obsidian,
    personal_streaks,
    planning,
    push,
    skills,
    stats,
    sync,
    tags,
    upload,
    vault,
    websocket,
)
from routers.integrations import github, google, spotify, strava
from services.auth_service import get_current_user
from fastapi import Depends
from services.response_cache import get_cache_stats
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


class RequestTimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = perf_counter()
        response = await call_next(request)
        duration_ms = (perf_counter() - start) * 1000
        response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"
        if duration_ms >= 500:
            logger.warning("[api] slow_request path=%s duration_ms=%.2f status=%s", request.url.path, duration_ms, response.status_code)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    _validate_secret_key()
    init_db()
    logger.info("[api] init_db complete")
    yield


def _validate_secret_key() -> None:
    """Abort startup if SECRET_KEY is a known public placeholder.

    An empty SECRET_KEY is allowed: it puts the app into the first-time setup
    flow (no tokens can be issued/verified, all auth-protected endpoints
    return 401 until `/config/setup` is completed). But a placeholder value
    that is public in the repo would let anyone forge JWTs, so we refuse to
    boot in that case. See issue #322.
    """
    from services.setup_state import SECRET_KEY_PLACEHOLDERS

    if settings.secret_key in SECRET_KEY_PLACEHOLDERS and settings.secret_key:
        # Non-empty placeholder (e.g. "dev_secret_change_me") — never allowed.
        raise RuntimeError(
            f"SECRET_KEY is set to a known public placeholder ({settings.secret_key!r}). "
            "Generate a real one with `openssl rand -hex 32` and set it in .env, "
            "or leave it empty to use the first-time setup flow."
        )


app = FastAPI(
    title="Joidy API",
    version="0.1.0",
    description=(
        "Joidy — Personal Knowledge Management API with gamification.\n\n"
        "Manages notes, tags, goals, skills, gamification (XP/streaks/plant stages), "
        "and integrations (GitHub, Obsidian vault sync).\n\n"
        "## Key Features\n"
        "- **Notes**: CRUD with WikiLink parsing, tag extraction, and AI embeddings\n"
        "- **Goals**: Temporal goals with rollover/snowball failure modes\n"
        "- **Gamification**: XP events, streaks, plant growth stages\n"
        "- **Skills**: Auto-generated skill tree from tag usage\n"
        "- **Graph**: Tag co-occurrence knowledge graph\n"
    ),
    lifespan=lifespan,
    openapi_tags=[
        {"name": "notes", "description": "Note CRUD, tags, WikiLinks, and AI embeddings"},
        {"name": "tags", "description": "Tag management and knowledge graph"},
        {"name": "goals", "description": "Goal tracking with temporal and failure modes"},
        {"name": "gamification", "description": "XP, streaks, plant stages, and activity tracking"},
        {"name": "skills", "description": "Auto-generated skill tree from tag usage"},
        {"name": "config", "description": "Application configuration management"},
        {"name": "planning", "description": "Planning and scheduling"},
        {"name": "github", "description": "GitHub integration (issues, PRs, OAuth)"},
        {"name": "vault", "description": "Obsidian vault sync status"},
        {"name": "ai", "description": "AI classification and RAG endpoints"},
        {"name": "personal_streaks", "description": "Personal streak tracking and analytics"},
    ],
)

app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(RateLimitMiddleware)

def _get_cors_origins() -> list[str]:
    """Return allowed CORS origins based on environment.

    Never returns ``["*"]``: a wildcard origin combined with
    ``allow_credentials=True`` violates the CORS spec and lets any website
    make credentialed requests. In development we list the concrete
    localhost origins the frontend uses instead. Set
    ``CORS_ALLOWED_ORIGINS`` explicitly for non-default ports or custom
    hosts. See issue #326.
    """
    if settings.cors_allowed_origins:
        return [o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()]
    if settings.app_env == "production":
        return []
    # Development fallback: concrete localhost origins (default frontend port).
    return ["http://localhost:3000", "http://127.0.0.1:3000"]


_cors_origins = _get_cors_origins()
if "*" in _cors_origins:
    logger.warning(
        "[api] CORS allow_origins contains '*' — never combine with "
        "allow_credentials=True (spec violation). See issue #326."
    )
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=settings.app_env == "production",
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIdMiddleware)

app.include_router(notes.router, dependencies=[Depends(get_current_user)])
app.include_router(config.router)
app.include_router(metrics.router, dependencies=[Depends(get_current_user)])
app.include_router(tags.router, dependencies=[Depends(get_current_user)])
app.include_router(skills.router, dependencies=[Depends(get_current_user)])
app.include_router(goals.router, dependencies=[Depends(get_current_user)])
app.include_router(gamification.router, dependencies=[Depends(get_current_user)])
app.include_router(personal_streaks.router, dependencies=[Depends(get_current_user)])
app.include_router(push.router, dependencies=[Depends(get_current_user)])
app.include_router(github.router, dependencies=[Depends(get_current_user)])
app.include_router(google.router, dependencies=[Depends(get_current_user)])
app.include_router(strava.router, dependencies=[Depends(get_current_user)])
app.include_router(spotify.router, dependencies=[Depends(get_current_user)])
app.include_router(vault.router, dependencies=[Depends(get_current_user)])
app.include_router(folders.router, dependencies=[Depends(get_current_user)])
app.include_router(ai.router, dependencies=[Depends(get_current_user)])
app.include_router(planning.router, dependencies=[Depends(get_current_user)])
app.include_router(websocket.router)
app.include_router(obsidian.router)
app.include_router(auth.router)
app.include_router(export.router, dependencies=[Depends(get_current_user)])
app.include_router(stats.router, dependencies=[Depends(get_current_user)])
app.include_router(sync.router, dependencies=[Depends(get_current_user)])
app.include_router(upload.router, dependencies=[Depends(get_current_user)])

# Ensure the upload directory exists before serving it.
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.get("/health")
def health():
    return {"status": "ok", "service": "joidy-api"}


@app.get("/health/ready")
def health_ready():
    """Comprehensive health check for orchestration (Kubernetes, Docker)."""
    from database import engine
    from sqlalchemy import text

    checks = {"database": "unknown", "cache": "unknown", "ai_service": "unknown"}

    # Database check
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)[:50]}"

    # Cache check (in-memory)
    try:
        from services.response_cache import get_cache_stats
        stats = get_cache_stats()
        checks["cache"] = "ok" if stats.get("initialized") else "degraded"
    except Exception as e:
        checks["cache"] = f"error: {str(e)[:50]}"

    # AI service check — short timeout to avoid blocking the health probe
    # while still detecting real outages (the previous implementation was a
    # hardcoded "ok" stub that masked a broken ai-service).
    try:
        import httpx
        with httpx.Client(timeout=2.0) as client:
            r = client.get(f"{settings.ai_service_url}/health")
            if r.status_code == 200:
                body = r.json()
                # Distinguish "alive" from "fully functional": if the ai-service
                # reports "degraded" (e.g. configured provider not available),
                # surface that here too.
                checks["ai_service"] = body.get("status", "ok")
            else:
                checks["ai_service"] = f"error: HTTP {r.status_code}"
    except Exception as e:
        checks["ai_service"] = f"unavailable: {str(e)[:40]}"

    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
    }


@app.get("/health/cache")
def health_cache():
    """Cache performance metrics for monitoring."""
    return get_cache_stats()


@app.get("/debug", dependencies=[Depends(get_current_user)])
def debug_info():
    """Debug endpoint with detailed system information.

    Only available when `APP_ENV=development`. In production this returns 404
    so the endpoint (and the operational data it exposes) is not discoverable
    by an authenticated attacker. See issue #327.
    """
    if settings.app_env != "development":
        raise HTTPException(status_code=404, detail="Not Found")

    from datetime import datetime, timezone

    debug_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "app_env": settings.app_env,
    }

    # Database info
    try:
        from database import engine
        from sqlalchemy import text

        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    (SELECT COUNT(*) FROM notes) as notes_count,
                    (SELECT COUNT(*) FROM tags) as tags_count,
                    (SELECT COUNT(*) FROM skills) as skills_count,
                    (SELECT COUNT(*) FROM goals) as goals_count,
                    (SELECT COUNT(*) FROM embedding_failures) as embeddings_failed
            """)).fetchone()

            debug_data["database"] = {
                "notes": result[0],
                "tags": result[1],
                "skills": result[2],
                "goals": result[3],
                "embedding_failures": result[4],
            }
    except Exception as e:
        debug_data["database"] = {"error": str(e)[:100]}

    # Cache stats
    try:
        from services.response_cache import get_cache_stats
        debug_data["cache"] = get_cache_stats()
    except Exception as e:
        debug_data["cache"] = {"error": str(e)[:100]}

    # Recent errors
    try:
        from database import SessionLocal
        from models.embedding_failures import EmbeddingFailure

        with SessionLocal() as db:
            recent_failures = db.query(EmbeddingFailure).order_by(
                EmbeddingFailure.last_error.desc()
            ).limit(5).all()

            debug_data["recent_failures"] = [
                {
                    "note_id": f.note_id,
                    "attempts": f.attempts,
                    "last_error": f.last_error,
                    "next_retry": f.next_retry_at.isoformat() if f.next_retry_at else None
                }
                for f in recent_failures
            ]
    except Exception as e:
        debug_data["recent_failures"] = {"error": str(e)[:100]}

    # Gamification stats
    try:
        from database import SessionLocal
        from models.gamification import UserStats

        with SessionLocal() as db:
            stats = db.query(UserStats).filter(UserStats.id == 1).first()
            if stats:
                debug_data["gamification"] = {
                    "total_xp": stats.total_xp,
                    "current_streak": stats.current_streak,
                    "plant_stage": stats.plant_stage,
                    "last_activity": stats.last_activity_date.isoformat() if stats.last_activity_date else None
                }
    except Exception as e:
        debug_data["gamification"] = {"error": str(e)[:100]}

    return debug_data


@app.get("/")
def root():
    return {"name": "Joidy API", "version": "0.1.0", "docs": "/docs"}
