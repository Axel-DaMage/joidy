from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from gemini_client import embed_text, classify_note, rag_query, embedding_to_bytes
from config import settings

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
    return {
        "status": "ok", 
        "service": "joidy-ai", 
        "ai_enabled": bool(settings.gemini_api_key)
    }


@app.post("/embed")
async def embed(req: EmbedRequest):
    if not settings.gemini_api_key:
        return {"status": "disabled", "note_id": req.note_id}
    
    try:
        vector = await embed_text(req.content)
        return {
            "status": "success", 
            "note_id": req.note_id, 
            "embedding": vector
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/classify")
async def classify(req: ClassifyRequest):
    if not settings.gemini_api_key:
        return {"status": "disabled", "note_id": req.note_id, "suggestions": []}
    
    try:
        suggestions = await classify_note(req.content, req.existing_tags)
        return {
            "status": "success", 
            "note_id": req.note_id, 
            "suggestions": suggestions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/usage")
def usage():
    return {"ai_enabled": bool(settings.gemini_api_key), "estimated_cost_usd": 0}
