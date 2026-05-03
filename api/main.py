from contextlib import asynccontextmanager
from time import perf_counter
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from database import init_db
from logging_config import setup_logging
from routers import ai, gamification, goals, notes, personal_streaks, skills, tags, vault, planning
from routers.integrations import github


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


app = FastAPI(title="Joidy API", version="0.1.0", lifespan=lifespan)

app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(RequestTimingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notes.router)
app.include_router(tags.router)
app.include_router(skills.router)
app.include_router(goals.router)
app.include_router(gamification.router)
app.include_router(personal_streaks.router)
app.include_router(github.router)
app.include_router(vault.router)
app.include_router(ai.router)
app.include_router(planning.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "joidy-api"}


@app.get("/")
def root():
    return {"name": "Joidy API", "version": "0.1.0", "docs": "/docs"}
