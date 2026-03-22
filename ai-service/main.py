from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from cost_tracker import get_monthly_stats, record_usage
from database import find_similar_notes, get_db, store_embedding
from gemini_client import classify_note, embed_text, rag_query


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.gemini_api_key:
        print("WARNING: GEMINI_API_KEY not set — AI features disabled")
    yield


app = FastAPI(title="Joidy AI Service", version="0.1.0", lifespan=lifespan)


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
    return {"status": "ok", "service": "joidy-ai", "api_key_set": bool(settings.gemini_api_key)}


@app.post("/embed")
async def embed(req: EmbedRequest):
    if not settings.gemini_api_key:
        return {"status": "skipped", "reason": "no api key"}
    try:
        embedding = await embed_text(req.content)
        store_embedding(req.note_id, embedding)
        record_usage("embed", input_tokens=len(req.content.split()) * 4)
        return {"status": "ok", "note_id": req.note_id, "dimensions": len(embedding)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/classify")
async def classify(req: ClassifyRequest):
    if not settings.gemini_api_key:
        return {"status": "skipped", "suggestions": []}
    try:
        suggestions = await classify_note(req.content, req.existing_tags)
        record_usage(
            "classify",
            input_tokens=len(req.content.split()) * 4 + 200,
            output_tokens=50,
        )
        return {"status": "ok", "note_id": req.note_id, "suggestions": suggestions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search")
async def semantic_search(req: RAGRequest):
    if not settings.gemini_api_key:
        return {"results": []}
    try:
        embedding = await embed_text(req.question)
        similar = find_similar_notes(embedding, limit=req.top_k)
        record_usage("search", input_tokens=len(req.question.split()) * 4)
        return {"results": similar}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rag")
async def ask(req: RAGRequest):
    """RAG: find relevant notes and answer the question."""
    if not settings.gemini_api_key:
        return {"answer": "API key no configurada.", "sources": []}
    try:
        embedding = await embed_text(req.question)
        similar = find_similar_notes(embedding, limit=req.top_k)

        # Fetch note content from DB
        import sqlite3
        from pathlib import Path
        conn = sqlite3.connect("/data/db/joidy.db")
        chunks = []
        for s in similar:
            row = conn.execute(
                "SELECT title, content FROM notes WHERE id = ?", (s["note_id"],)
            ).fetchone()
            if row:
                chunks.append(f"**{row[0]}**\n{row[1]}")
        conn.close()

        answer = await rag_query(req.question, chunks)
        record_usage("rag", input_tokens=sum(len(c.split()) for c in chunks) * 4 + 100, output_tokens=200)
        return {"answer": answer, "sources": [s["note_id"] for s in similar]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/usage")
def usage():
    return get_monthly_stats()
