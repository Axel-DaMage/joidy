import logging
from contextlib import asynccontextmanager
from time import perf_counter

from config import settings
from database import init_db
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from logging_config import setup_logging
from middleware.metrics import MetricsMiddleware, get_metrics_collector
from middleware.rate_limit import RateLimitMiddleware
from routers import (
    ai,
    auth,
    config,
    export,
    gamification,
    goals,
    notes,
    personal_streaks,
    planning,
    skills,
    stats,
    tags,
    vault,
    websocket,
)
from routers.integrations import github
from services.auth_service import get_current_user
from fastapi import Depends
from services.response_cache import get_cache_stats
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

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
    yield


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
    """Return allowed CORS origins based on environment."""
    if settings.app_env == "production":
        origins = settings.cors_allowed_origins
        return [o.strip() for o in origins.split(",") if o.strip()] if origins else []
    return ["*"]  # Development: allow all


_cors_origins = _get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=settings.app_env == "production",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notes.router, dependencies=[Depends(get_current_user)])
app.include_router(config.router, dependencies=[Depends(get_current_user)])
app.include_router(tags.router, dependencies=[Depends(get_current_user)])
app.include_router(skills.router, dependencies=[Depends(get_current_user)])
app.include_router(goals.router, dependencies=[Depends(get_current_user)])
app.include_router(gamification.router, dependencies=[Depends(get_current_user)])
app.include_router(personal_streaks.router, dependencies=[Depends(get_current_user)])
app.include_router(github.router, dependencies=[Depends(get_current_user)])
app.include_router(vault.router, dependencies=[Depends(get_current_user)])
app.include_router(ai.router, dependencies=[Depends(get_current_user)])
app.include_router(planning.router, dependencies=[Depends(get_current_user)])
app.include_router(websocket.router)
app.include_router(auth.router)
app.include_router(export.router, dependencies=[Depends(get_current_user)])
app.include_router(stats.router, dependencies=[Depends(get_current_user)])


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

    # AI service check
    try:
        import httpx
        resp = httpx.get(f"{settings.ai_service_url}/health", timeout=2.0)
        checks["ai_service"] = "ok" if resp.status_code == 200 else f"degraded: {resp.status_code}"
    except Exception:
        checks["ai_service"] = "unavailable"

    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
    }


@app.get("/health/cache")
def health_cache():
    """Cache performance metrics for monitoring."""
    return get_cache_stats()


@app.get("/metrics")
def metrics():
    """Request metrics for monitoring."""
    return get_metrics_collector().get_metrics()


@app.get("/debug")
def debug_info():
    """Debug endpoint with detailed system information."""
    import os
    import sys
    from datetime import datetime

    debug_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "python_version": sys.version,
        "platform": os.name,
        "env": {
            k: v for k, v in os.environ.items()
            if k in ("PYTHON_ENV", "DEBUG", "LOG_LEVEL")
        },
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
