import logging
from contextlib import asynccontextmanager

from circuit_breaker import llm_circuit_breaker, emb_circuit_breaker, CircuitBreakerError
from clients import get_embedding_client, get_llm_client
from clients.prompts import CLASSIFY_PROMPT, RAG_PROMPT
from config import settings
from fastapi import FastAPI, HTTPException
from logging_config import get_correlation_id, set_correlation_id, setup_logging
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logging.getLogger(__name__).info("[ai-service] Starting up")
    yield
    logging.getLogger(__name__).info("[ai-service] Shutting down")


app = FastAPI(title="Joidy AI Service", version="0.2.0", lifespan=lifespan)


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        set_correlation_id(request.headers.get("X-Request-ID", ""))
        response = await call_next(request)
        cid = get_correlation_id()
        if cid:
            response.headers["X-Request-ID"] = cid
        return response


app.add_middleware(CorrelationMiddleware)


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
        vector = await emb_circuit_breaker.call(client.embed, req.content)

        # Save vector embedding to shared SQLite database
        from database import store_embedding
        store_embedding(req.note_id, vector)

        return {
            "status": "success",
            "note_id": req.note_id,
            "embedding": vector,
            "provider": client.provider_name,
        }
    except CircuitBreakerError as e:
        return {"status": "circuit_open", "note_id": req.note_id, "error": str(e)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/classify")
async def classify(req: ClassifyRequest):
    if not settings.is_ai_enabled:
        return {"status": "disabled", "note_id": req.note_id, "suggestions": [], "error": "No AI provider configured"}

    try:
        client = get_llm_client()
        suggestions = await llm_circuit_breaker.call(client.classify, req.content, req.existing_tags, CLASSIFY_PROMPT)
        return {
            "status": "success",
            "note_id": req.note_id,
            "suggestions": suggestions,
            "provider": client.provider_name,
        }
    except CircuitBreakerError as e:
        return {"status": "circuit_open", "note_id": req.note_id, "suggestions": [], "error": str(e)}
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
        # 1. Get embedding for the question
        emb_client = get_embedding_client()
        question_vector = await emb_circuit_breaker.call(emb_client.embed, req.question)

        # 2. Find similar note IDs from SQLite vector database
        from database import engine, find_similar_notes
        similar = find_similar_notes(question_vector, limit=req.top_k)

        # 3. Retrieve note titles & contents to build LLM context
        context_chunks = []
        with engine.connect() as conn:
            for item in similar:
                nid = item["note_id"]
                # Use raw SQL to fetch from the shared SQLite DB
                row = conn.execute(
                    "SELECT title, content FROM notes WHERE id = ?",  # type: ignore
                    (nid,),
                ).fetchone()
                if row:
                    context_chunks.append(f"Nota: {row[0]}\nContenido: {row[1]}")

        client = get_llm_client()
        answer = await llm_circuit_breaker.call(
            client.generate,
            prompt=RAG_PROMPT.format(question=req.question, context="\n\n---\n\n".join(context_chunks)),
            temperature=0.2,
            max_tokens=512,
        )
        return {
            "status": "success",
            "answer": answer,
            "provider": client.provider_name,
        }
    except CircuitBreakerError as e:
        return {"status": "circuit_open", "answer": "El proveedor de IA se encuentra temporalmente no disponible.", "error": str(e)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
