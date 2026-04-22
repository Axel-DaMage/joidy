from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from logging_config import setup_logging
from routers import ai, gamification, goals, notes, personal_streaks, skills, tags, vault
from routers.integrations import github


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_db()
    yield


app = FastAPI(title="Joidy API", version="0.1.0", lifespan=lifespan)

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


@app.get("/health")
def health():
    return {"status": "ok", "service": "joidy-api"}


@app.get("/")
def root():
    return {"name": "Joidy API", "version": "0.1.0", "docs": "/docs"}
