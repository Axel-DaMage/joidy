"""
Joidy AI Service — STUB MODE (AI disabled)
All endpoints return empty/no-op responses.
To enable AI: set GEMINI_API_KEY in .env and set AI_ENABLED=true
"""

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Joidy AI Service", version="0.1.0")


class EmbedRequest(BaseModel):
    note_id: int
    content: str


class ClassifyRequest(BaseModel):
    note_id: int
    content: str
    existing_tags: list[str] = []


class RAGRequest(BaseModel):
    question: str
    top_k: int = 5


@app.get("/health")
def health():
    return {"status": "ok", "service": "joidy-ai", "ai_enabled": False}


@app.post("/embed")
def embed(req: EmbedRequest):
    return {"status": "disabled", "note_id": req.note_id}


@app.post("/classify")
def classify(req: ClassifyRequest):
    return {"status": "disabled", "note_id": req.note_id, "suggestions": []}


@app.post("/search")
def semantic_search(req: RAGRequest):
    return {"results": []}


@app.post("/rag")
def ask(req: RAGRequest):
    return {"answer": "IA no habilitada. Agrega GEMINI_API_KEY al .env para activarla.", "sources": []}


@app.get("/usage")
def usage():
    return {"ai_enabled": False, "estimated_cost_usd": 0}
