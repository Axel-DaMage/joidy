import logging
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter

from config import settings
from database import init_db
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from logging_config import setup_logging
from middleware.metrics import MetricsMiddleware
from middleware.rate_limit import RateLimitMiddleware
from middleware.request_id import RequestIdMiddleware
from routers import (
    folders,
    ai,
    analytics,
    auth,
    config,
    export,
    gamification,
    goals,
    metrics,
    mood,
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
    init_db()
    logger.info("Database initialization complete")

    # Auto-restore goals from vault if DB has none (#504)
    try:
        from database import SessionLocal
        from models.goal import Goal
        from services.joidy_vault_writer import restore_goals_from_vault

        with SessionLocal() as db:
            if db.query(Goal).count() == 0:
                result = restore_goals_from_vault(db)
                if result["restored"] > 0:
                    logger.info("Restored %d goals from vault", result["restored"])
    except Exception:
        logger.exception("Failed to auto-restore goals from vault")

    yield


class CorsSafetyMiddleware(BaseHTTPMiddleware):
    """Ensure CORS headers on ALL responses, even during errors.

    Respects the configured CORS origins instead of always using ``*``.
    In production with specific origins, only the request's Origin is
    echoed back if it matches the allowlist.
    """

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled exception in request: %s %s", request.method, request.url.path)
            from starlette.responses import JSONResponse
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )
        # Only add CORS headers if CORSMiddleware hasn't already set them
        # (CORSMiddleware runs first in the stack, but may skip on error paths).
        if "Access-Control-Allow-Origin" not in response.headers:
            if "*" in _cors_origins:
                response.headers["Access-Control-Allow-Origin"] = "*"
            else:
                request_origin = request.headers.get("origin")
                if request_origin and request_origin in _cors_origins:
                    response.headers["Access-Control-Allow-Origin"] = request_origin
                    response.headers.setdefault("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
                    response.headers.setdefault("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Request-Id")
        return response


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
        {"name": "mood", "description": "Daily mood tracking and analytics"},
    ],
)

app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(RateLimitMiddleware)

def _get_cors_origins() -> list[str]:
    """Return allowed CORS origins based on environment."""
    if settings.cors_allowed_origins:
        return [o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()]
    if settings.app_env == "production":
        return []
    return ["*"]  # Development fallback: allow all


_cors_origins = _get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=settings.app_env == "production",
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CorsSafetyMiddleware)
app.add_middleware(RequestIdMiddleware)

app.include_router(notes.router, dependencies=[Depends(get_current_user)])
app.include_router(config.router)
app.include_router(metrics.router, dependencies=[Depends(get_current_user)])
app.include_router(mood.router, dependencies=[Depends(get_current_user)])
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
app.include_router(analytics.router, dependencies=[Depends(get_current_user)])
app.include_router(sync.router, dependencies=[Depends(get_current_user)])
app.include_router(upload.router, dependencies=[Depends(get_current_user)])

# Ensure the upload directory exists before serving it. This is best-effort:
# uploads are a non-critical feature, so an unwritable path (read-only mount,
# host/container UID mismatch) must degrade rather than abort startup and take
# down notes, goals and sync with it (#624).
_uploads_available = True
try:
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
except OSError:
    _uploads_available = False
    logger.warning(
        "Uploads disabled — could not create upload_dir '%s'", settings.upload_dir, exc_info=True
    )


class SafeStaticFiles(StaticFiles):
    """StaticFiles that forces Content-Disposition: attachment for SVG files."""

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if path.lower().endswith(".svg"):
            response.headers["Content-Disposition"] = "attachment"
            response.headers["Content-Type"] = "image/svg+xml"
        return response


# StaticFiles resolves the directory eagerly, so only mount when it exists.
if _uploads_available:
    app.mount("/uploads", SafeStaticFiles(directory=settings.upload_dir), name="uploads")


@app.get("/health")
def health():
    """Liveness + basic dependency check.

    Unlike ``/health/ready`` (which performs a full readiness probe including
    the AI service), this endpoint verifies only the core dependency (database)
    so it can be used as a liveness probe that still reflects real outages.
    """
    from database import engine
    from sqlalchemy import text

    checks = {"database": "unknown"}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)[:50]}"

    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "ok" if all_ok else "degraded",
        "service": "joidy-api",
        "checks": checks,
    }


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
    """Debug endpoint with safe diagnostic information."""
    import sys
    from datetime import datetime, timezone

    debug_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version,
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
    except Exception:
        debug_data["database"] = {"error": "unavailable"}

    # Cache stats
    try:
        from services.response_cache import get_cache_stats
        debug_data["cache"] = get_cache_stats()
    except Exception:
        debug_data["cache"] = {"error": "unavailable"}

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
                    "next_retry": f.next_retry_at.isoformat() if f.next_retry_at else None
                }
                for f in recent_failures
            ]
    except Exception:
        debug_data["recent_failures"] = {"error": "unavailable"}

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
    except Exception:
        debug_data["gamification"] = {"error": "unavailable"}

    return debug_data


@app.get("/")
def root():
    return {"name": "Joidy API", "version": "0.1.0", "docs": "/docs"}
