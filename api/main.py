from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routers import gamification, goals, notes, skills, tags, vault
from routers.integrations import github


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Joidy API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notes.router)
app.include_router(tags.router)
app.include_router(skills.router)
app.include_router(goals.router)
app.include_router(gamification.router)
app.include_router(github.router)
app.include_router(vault.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "joidy-api"}


@app.get("/")
def root():
    return {"name": "Joidy API", "version": "0.1.0", "docs": "/docs"}
