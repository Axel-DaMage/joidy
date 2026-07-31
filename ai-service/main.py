import logging
from contextlib import asynccontextmanager

from circuit_breaker import llm_circuit_breaker, emb_circuit_breaker, CircuitBreakerError
from clients import get_embedding_client, get_llm_client
from clients.prompts import CHAT_SYSTEM_PROMPT, CLASSIFY_PROMPT, RAG_PROMPT
from config import settings
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from logging_config import get_correlation_id, set_correlation_id, setup_logging
from pydantic import BaseModel
from rate_limiter import get_limiter
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


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


# CORS: restrict to configured origins, or allow all in development
_cors_origins = (
    [o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()]
    if settings.cors_allowed_origins
    else (["*"] if settings.app_env != "production" else [])
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=settings.app_env == "production",
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Internal-Secret"],
)


class InternalAuthMiddleware(BaseHTTPMiddleware):
    """Validate internal secret for non-health endpoints.

    If INTERNAL_SECRET is configured, all endpoints except /health
    require an X-Internal-Secret header matching the configured value.
    """

    async def dispatch(self, request: Request, call_next):
        if settings.internal_secret and request.url.path != "/health":
            provided = request.headers.get("X-Internal-Secret", "")
            if provided != settings.internal_secret:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Forbidden: invalid internal secret"},
                )
        return await call_next(request)


app.add_middleware(InternalAuthMiddleware)


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


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatContext(BaseModel):
    goals: list[dict] = []
    streaks: list[dict] = []
    xp: int | None = None
    top_tags: list[str] = []
    recent_notes: list[str] = []


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    context: ChatContext | None = None


def _get_provider_info():
    available = settings.available_providers
    llm_provider, llm_model = settings.llm_model.split(":", 1) if ":" in settings.llm_model else ("gemini", settings.llm_model)
    emb_provider, emb_model = settings.embedding_model.split(":", 1) if ":" in settings.embedding_model else ("gemini", settings.embedding_model)
    return {
        "llm": {"provider": llm_provider, "model": llm_model, "available": llm_provider in available},
        "embedding": {"provider": emb_provider, "model": emb_model, "available": emb_provider in available},
        "available": available,
    }


@app.get("/health")
def health():
    provider_info = _get_provider_info()
    # The service is "degraded" if the configured LLM/embedding provider is
    # not actually available (e.g. GEMINI_API_KEY not set but model is gemini:*).
    llm_ok = provider_info["llm"]["available"]
    emb_ok = provider_info["embedding"]["available"]
    status = "ok" if (llm_ok and emb_ok) else "degraded"
    return {
        "status": status,
        "service": "joidy-ai",
        "ai_enabled": settings.is_ai_enabled,
        "provider": provider_info,
    }


@app.get("/providers")
def providers():
    return {
        "available": settings.available_providers,
        "configured": {name: True for name in settings.provider_config},
        "llm_model": settings.llm_model,
        "embedding_model": settings.embedding_model,
    }

def _build_chat_system_prompt(ctx: ChatContext | None) -> str:
    """Build a system prompt that includes the user's personal context."""
    if ctx is None:
        return CHAT_SYSTEM_PROMPT.format(personal_context="Sin contexto adicional disponible.")
    lines: list[str] = []
    if ctx.goals:
        goal_lines = []
        for g in ctx.goals[:10]:
            title = g.get("title", "Meta")
            progress = g.get("progress_pct")
            target = g.get("target_value")
            current = g.get("current_value")
            state = g.get("state", "ACTIVE")
            if progress is not None:
                goal_lines.append(f"- {title} ({state}): {progress}% — {current}/{target}")
            else:
                goal_lines.append(f"- {title} ({state})")
        lines.append("Metas activas:\n" + "\n".join(goal_lines))
    if ctx.streaks:
        streak_lines = []
        for st in ctx.streaks[:5]:
            name = st.get("name", "Racha")
            current = st.get("current_streak", 0)
            streak_lines.append(f"- {name}: {current} días")
        lines.append("Rachas:\n" + "\n".join(streak_lines))
    if ctx.xp is not None:
        lines.append(f"XP total: {ctx.xp}")
    if ctx.top_tags:
        lines.append("Tags principales (intereses): " + ", ".join(ctx.top_tags[:5]))
    if ctx.recent_notes:
        lines.append("Notas recientes (títulos):\n- " + "\n- ".join(ctx.recent_notes[:10]))
    personal_context = "\n\n".join(lines) if lines else "Sin contexto adicional disponible."
    return CHAT_SYSTEM_PROMPT.format(personal_context=personal_context)


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
        return {"status": "circuit_open", "note_id": req.note_id, "error": "Circuit breaker open"}
    except Exception:
        raise HTTPException(status_code=500, detail="Embedding failed")


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
        return {"status": "circuit_open", "note_id": req.note_id, "suggestions": [], "error": "Circuit breaker open"}
    except Exception:
        raise HTTPException(status_code=500, detail="Classification failed")


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
        # Limit context size to reduce PII exposure and token usage
        MAX_CONTEXT_NOTES = 5
        MAX_NOTE_CHARS = 2000
        context_chunks = []
        with engine.connect() as conn:
            for item in similar[:MAX_CONTEXT_NOTES]:
                nid = item["note_id"]
                # Use raw SQL to fetch from the shared SQLite DB
                row = conn.execute(
                    "SELECT title, content FROM notes WHERE id = ?",  # type: ignore
                    (nid,),
                ).fetchone()
                if row:
                    note_content = (row[1] or "")[:MAX_NOTE_CHARS]
                    context_chunks.append(f"Nota: {row[0]}\nContenido: {note_content}")

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
        return {"status": "circuit_open", "answer": "El proveedor de IA se encuentra temporalmente no disponible.", "error": "Circuit breaker open"}
    except Exception:
        raise HTTPException(status_code=500, detail="RAG failed")


@app.post("/chat")
async def chat(req: ChatRequest):
    if not settings.is_ai_enabled:
        return {
            "status": "disabled",
            "response": "El asistente de IA no está configurado. Añade una API key para activarlo.",
            "suggestions": [],
        }
    if not req.messages:
        raise HTTPException(status_code=422, detail="messages must not be empty")
    limiter = get_limiter()
    await limiter.acquire()
    try:
        system_prompt = _build_chat_system_prompt(req.context)
        history = "\n\n".join(
            f"{'Usuario' if m.role == 'user' else 'Asistente'}: {m.content}"
            for m in req.messages[:-1]
        )
        last = req.messages[-1]
        if last.role != "user":
            raise HTTPException(status_code=422, detail="last message must be from user")
        prompt = f"{history}\n\nUsuario: {last.content}\n\nAsistente:" if history else f"Usuario: {last.content}\n\nAsistente:"
        client = get_llm_client()
        response = await llm_circuit_breaker.call(
            client.generate,
            prompt=prompt,
            temperature=0.7,
            max_tokens=1024,
            system_prompt=system_prompt,
        )
        suggestions = _build_suggestions(last.content, req.context)
        return {
            "status": "success",
            "response": response.strip(),
            "suggestions": suggestions,
            "provider": client.provider_name,
        }
    except CircuitBreakerError:
        return {
            "status": "circuit_open",
            "response": "El proveedor de IA se encuentra temporalmente no disponible. Intenta de nuevo en unos minutos.",
            "suggestions": [],
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Chat failed")


def _build_suggestions(user_message: str, ctx: ChatContext | None) -> list[str]:
    """Return a few follow-up prompt suggestions based on user context."""
    suggestions: list[str] = []
    if ctx and ctx.goals:
        suggestions.append("¿Cómo voy con mis metas activas?")
    if ctx and ctx.streaks:
        suggestions.append("Dame ideas para mantener mis rachas")
    if ctx and ctx.recent_notes:
        suggestions.append("Resume mis notas recientes")
    if ctx and ctx.top_tags:
        suggestions.append(f"Háblame sobre {ctx.top_tags[0]}")
    if not suggestions:
        suggestions = [
            "¿Qué debería aprender esta semana?",
            "Ayúdame a definir una nueva meta",
            "¿Cómo organizo mejor mis notas?",
        ]
    return suggestions[:3]
