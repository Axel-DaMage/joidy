from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from clients import get_llm_client, get_embedding_client
from clients.prompts import CLASSIFY_PROMPT, RAG_PROMPT
from clients.gemini import embedding_to_bytes
from config import settings

app = FastAPI(title="Joidy AI Service", version="0.2.0")


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


def _get_provider_info():
    available = settings.available_providers
    llm_provider, llm_model = settings.llm_model.split(":", 1) if ":" in settings.llm_model else ("gemini", settings.llm_model)
    emb_provider, emb_model = settings.embedding_model.split(":", 1) if ":" in settings.embedding_model else ("gemini", settings.embedding_model)
    return {
        "llm": {"provider": llm_provider, "model": llm_model},
        "embedding": {"provider": emb_provider, "model": emb_model},
        "available": available,
    }


@app.get("/health")
def health():
    provider_info = _get_provider_info()
    return {
        "status": "ok",
        "service": "joidy-ai",
        "ai_enabled": settings.is_ai_enabled,
        "provider": provider_info,
    }


@app.get("/providers")
def providers():
    return {
        "available": settings.available_providers,
        "configured": settings.provider_config,
        "llm_model": settings.llm_model,
        "embedding_model": settings.embedding_model,
    }


@app.post("/embed")
async def embed(req: EmbedRequest):
    if not settings.is_ai_enabled:
        return {"status": "disabled", "note_id": req.note_id, "error": "No AI provider configured"}

    try:
        client = get_embedding_client()
        vector = await client.embed(req.content)
        return {
            "status": "success",
            "note_id": req.note_id,
            "embedding": vector,
            "provider": client.provider_name,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/classify")
async def classify(req: ClassifyRequest):
    if not settings.is_ai_enabled:
        return {"status": "disabled", "note_id": req.note_id, "suggestions": [], "error": "No AI provider configured"}

    try:
        client = get_llm_client()
        suggestions = await client.classify(req.content, req.existing_tags, CLASSIFY_PROMPT)
        return {
            "status": "success",
            "note_id": req.note_id,
            "suggestions": suggestions,
            "provider": client.provider_name,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/usage")
def usage():
    return {
        "ai_enabled": settings.is_ai_enabled,
        "available_providers": settings.available_providers,
        "estimated_cost_usd": 0,
    }


@app.post("/rag")
async def rag(req: RAGRequest):
    if not settings.is_ai_enabled:
        return {"status": "disabled", "answer": "No AI provider configured"}

    try:
        client = get_llm_client()
        context_chunks = []
        answer = await client.generate(
            prompt=RAG_PROMPT.format(question=req.question, context="\n\n---\n\n".join(context_chunks[:5])),
            temperature=0.2,
            max_tokens=512,
        )
        return {
            "status": "success",
            "answer": answer,
            "provider": client.provider_name,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))