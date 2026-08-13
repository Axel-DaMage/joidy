import logging
from contextlib import asynccontextmanager

from circuit_breaker import llm_circuit_breaker, emb_circuit_breaker, CircuitBreakerError
from clients import get_embedding_client, get_llm_client
from clients.prompts import CHAT_SYSTEM_PROMPT, CLASSIFY_PROMPT, RAG_PROMPT
from config import settings
from cost_tracker import get_monthly_stats, record_usage
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from logging_config import get_correlation_id, set_correlation_id, setup_logging
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field
from rate_limiter import get_limiter
from response_cache import cache_key, get_cache
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Prometheus metrics — exposed at /metrics for scraping (#406)
ai_embed_requests = Counter('ai_embed_requests_total', 'Embedding requests', ['provider'])
ai_embed_errors = Counter('ai_embed_errors_total', 'Embedding errors', ['provider'])
ai_embed_latency = Histogram('ai_embed_latency_seconds', 'Embedding latency', ['provider'])
ai_classify_requests = Counter('ai_classify_requests_total', 'Classification requests', ['provider'])
ai_classify_errors = Counter('ai_classify_errors_total', 'Classification errors', ['provider'])
ai_rag_requests = Counter('ai_rag_requests_total', 'RAG requests', ['provider'])
ai_rag_errors = Counter('ai_rag_errors_total', 'RAG errors', ['provider'])


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("[ai-service] Starting up")

    # Startup health check: ping configured providers and log availability (#568).
    # This does NOT block startup — it only logs the result so operators can
    # see which provider is actually reachable.
    if settings.is_ai_enabled:
        try:
            llm_client = get_llm_client()
            llm_healthy = await llm_client.health_check()
            logger.info(f"[ai-service] LLM provider '{llm_client.provider_name}' health: {'OK' if llm_healthy else 'UNREACHABLE'}")
        except Exception as exc:
            logger.warning(f"[ai-service] LLM health check failed: {exc}")

        try:
            emb_client = get_embedding_client()
            emb_healthy = await emb_client.health_check()
            logger.info(f"[ai-service] Embedding provider '{emb_client.provider_name}' health: {'OK' if emb_healthy else 'UNREACHABLE'}")
        except Exception as exc:
            logger.warning(f"[ai-service] Embedding health check failed: {exc}")
    else:
        logger.info("[ai-service] No AI providers configured — AI features disabled")

    yield
    logger.info("[ai-service] Shutting down")


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
        # /health and /metrics are always public so Prometheus can scrape
        # without needing the internal secret (#406).
        if settings.internal_secret and request.url.path not in ("/health", "/metrics"):
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
    content: str = Field(max_length=100_000)


class ClassifyRequest(BaseModel):
    note_id: int
    content: str = Field(max_length=10_000)
    existing_tags: list[str] = []


class RAGRequest(BaseModel):
    question: str = Field(max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token) for cost tracking."""
    return max(1, len(text) // 4)


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


def _has_fallback() -> bool:
    """Check if Ollama fallback is available for the configured primary provider."""
    available = settings.available_providers
    llm_provider = settings.llm_model.split(":", 1)[0] if ":" in settings.llm_model else "gemini"
    emb_provider = settings.embedding_model.split(":", 1)[0] if ":" in settings.embedding_model else "gemini"
    return "ollama" in available and (llm_provider != "ollama" or emb_provider != "ollama")


@app.get("/health")
async def health():
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
        "fallback_enabled": _has_fallback(),
    }


@app.get("/metrics")
def metrics():
    """Expose Prometheus-compatible metrics for scraping (#406)."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


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

    await get_limiter(settings.max_requests_per_minute).acquire()

    # Cache: identical content + model always yields the same vector, so skip
    # the provider call entirely when we have a hit.
    key = cache_key("embed", settings.embedding_model, req.content)
    cached = get_cache().get(key)

    try:
        if cached is not None:
            vector = cached
            provider_name = settings.embedding_model.split(":", 1)[0]
        else:
            client = get_embedding_client()
            vector = await emb_circuit_breaker.call(client.embed, req.content)
            provider_name = client.provider_name
            get_cache().set(key, vector)

        # Save vector embedding to shared PostgreSQL database
        from database import store_embedding
        store_embedding(req.note_id, vector)

        record_usage("embed", input_tokens=_estimate_tokens(req.content))

        return {
            "status": "success",
            "note_id": req.note_id,
            "embedding": vector,
            "provider": provider_name,
        }
    except CircuitBreakerError as e:
        return {"status": "circuit_open", "note_id": req.note_id, "error": "Circuit breaker open"}
    except Exception:
        raise HTTPException(status_code=500, detail="Embedding failed")


@app.post("/classify")
async def classify(req: ClassifyRequest):
    if not settings.is_ai_enabled:
        return {"status": "disabled", "note_id": req.note_id, "suggestions": [], "error": "No AI provider configured"}

    await get_limiter(settings.max_requests_per_minute).acquire()

    # Cache keyed on content + existing tags + model. Classify is often fired
    # repeatedly while editing, so this avoids burning provider quota.
    tags_key = ",".join(sorted(req.existing_tags))
    key = cache_key("classify", settings.llm_model, req.content, tags_key)
    cached = get_cache().get(key)

    try:
        if cached is not None:
            suggestions = cached
            provider_name = settings.llm_model.split(":", 1)[0]
        else:
            client = get_llm_client()
            suggestions = await llm_circuit_breaker.call(
                client.classify, req.content, req.existing_tags, CLASSIFY_PROMPT
            )
            provider_name = client.provider_name
            get_cache().set(key, suggestions)

        record_usage("classify", input_tokens=_estimate_tokens(req.content))

        return {
            "status": "success",
            "note_id": req.note_id,
            "suggestions": suggestions,
            "provider": provider_name,
        }
    except CircuitBreakerError as e:
        return {"status": "circuit_open", "note_id": req.note_id, "suggestions": [], "error": "Circuit breaker open"}
    except Exception:
        raise HTTPException(status_code=500, detail="Classification failed")


@app.get("/usage")
def usage():
    stats = get_monthly_stats()
    return {
        "ai_enabled": settings.is_ai_enabled,
        "available_providers": settings.available_providers,
        **stats,
    }


@app.post("/rag")
async def rag(req: RAGRequest):
    if not settings.is_ai_enabled:
        return {"status": "disabled", "answer": "No AI provider configured"}

    await get_limiter(settings.max_requests_per_minute).acquire()

    try:
        # 1. Get embedding for the question
        emb_client = get_embedding_client()
        question_vector = await emb_circuit_breaker.call(emb_client.embed, req.question)

        # 2. Find similar note IDs via pgvector cosine similarity
        from database import engine, find_similar_notes
        similar = find_similar_notes(question_vector, limit=req.top_k)

        # 3. Retrieve note titles & contents to build LLM context.
        # Use SQLAlchemy text() with named parameters — PostgreSQL does not
        # accept the SQLite "?" placeholder style (previously broken, #398).
        # Limit context size to reduce PII exposure and token usage.
        MAX_CONTEXT_NOTES = 5
        MAX_NOTE_CHARS = 2000
        context_chunks = []
        with engine.connect() as conn:
            for item in similar[:MAX_CONTEXT_NOTES]:
                nid = item["note_id"]
                row = conn.execute(
                    text("SELECT title, content FROM notes WHERE id = :nid"),
                    {"nid": nid},
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
        record_usage(
            "rag",
            input_tokens=_estimate_tokens(req.question) + sum(_estimate_tokens(c) for c in context_chunks),
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


class DailyRecapRequest(BaseModel):
    date: str  # YYYY-MM-DD
    notes_created: int = 0
    notes_edited: int = 0
    xp_gained: int = 0
    streak_maintained: bool = False
    goals_completed: int = 0
    focus_time_minutes: int = 0
    note_titles: list[str] = []


@app.post("/daily-recap")
async def daily_recap(req: DailyRecapRequest):
    """Generate a natural-language daily recap from structured activity data (#354).

    The API sends a summary of the day's activity; the AI service generates
    a reflective paragraph + 1-2 suggestions for tomorrow.
    """
    if not settings.is_ai_enabled:
        return {"status": "disabled", "recap": "", "suggestions": []}

    ai_classify_requests.labels(provider=settings.llm_model or 'unknown').inc()
    try:
        client = get_llm_client()
        titles_str = "\n".join(f"- {t}" for t in req.note_titles[:10]) or "(sin notas)"
        prompt = f"""Eres un asistente de productividad personal. Genera un resumen diario breve y motivador en español basado en esta actividad del día {req.date}:

- Notas creadas: {req.notes_created}
- Notas editadas: {req.notes_edited}
- XP ganada: {req.xp_gained}
- Racha mantenida: {'sí' if req.streak_maintained else 'no'}
- Objetivos completados: {req.goals_completed}
- Tiempo de enfoque: {req.focus_time_minutes} minutos

Títulos de notas creadas hoy:
{titles_str}

Genera:
1. Un párrafo (2-3 frases) que sintetice el día de forma natural y motivadora.
2. 1-2 sugerencias breves para mañana.

Responde en formato JSON: {{"recap": "...", "suggestions": ["...", "..."]}}"""
        response = await llm_circuit_breaker.call(
            client.generate,
            prompt=prompt,
            temperature=0.7,
            max_tokens=300,
        )

        # Try to parse JSON from the response; fall back to raw text
        import json
        try:
            parsed = json.loads(response)
            return {
                "status": "success",
                "recap": parsed.get("recap", response),
                "suggestions": parsed.get("suggestions", []),
                "provider": client.provider_name,
            }
        except (json.JSONDecodeError, TypeError):
            return {
                "status": "success",
                "recap": response,
                "suggestions": [],
                "provider": client.provider_name,
            }
    except CircuitBreakerError:
        return {"status": "circuit_open", "recap": "El proveedor de IA no está disponible.", "suggestions": []}
    except Exception:
        ai_classify_errors.labels(provider=settings.llm_model or 'unknown').inc()
        raise HTTPException(status_code=500, detail="Daily recap failed")


@app.post("/cluster")
async def cluster_notes(eps: float = 0.3, min_samples: int = 3, max_notes: int = 500):
    """Cluster notes by embedding similarity using DBSCAN (#393).

    Returns clusters of note IDs that share semantic themes, plus a
    representative title for each cluster (the note closest to the centroid).
    """
    from database import engine
    from sqlalchemy import text as sql_text

    with engine.connect() as conn:
        rows = conn.execute(
            sql_text("""
                SELECT ne.note_id, ne.embedding
                FROM note_embeddings ne
                JOIN notes n ON n.id = ne.note_id
                ORDER BY n.created_at DESC
                LIMIT :max_notes
            """),
            {"max_notes": max_notes},
        ).fetchall()

    if len(rows) < min_samples:
        return {"clusters": [], "total_notes": len(rows)}

    # Parse embeddings from pgvector string format
    import numpy as np
    note_ids = [r[0] for r in rows]
    embeddings = []
    for r in rows:
        vec_str = r[1] if isinstance(r[1], str) else str(r[1])
        vec = [float(x) for x in vec_str.strip('[]').split(',')]
        embeddings.append(vec)

    X = np.array(embeddings)

    # DBSCAN clustering — no need to specify number of clusters
    from sklearn.cluster import DBSCAN
    clustering = DBSCAN(eps=eps, min_samples=min_samples, metric='cosine').fit(X)
    labels = clustering.labels_

    # Build cluster results
    from collections import defaultdict
    clusters = defaultdict(list)
    for idx, label in enumerate(labels):
        if label != -1:  # -1 = noise
            clusters[label].append(note_ids[idx])

    # Fetch titles for representative notes (closest to centroid).
    # Use a single connection for all cluster lookups to avoid exhausting the
    # pool, and use parameterized placeholders to prevent SQL injection (#610).
    cluster_results = []
    with engine.connect() as conn:
        for label, ids in clusters.items():
            params = {f"id_{idx}": i for idx, i in enumerate(ids)}
            placeholders = ", ".join(f":id_{idx}" for idx in range(len(ids)))
            title_rows = conn.execute(
                sql_text(f"SELECT id, title FROM notes WHERE id IN ({placeholders})"),
                params,
            ).fetchall()
            title_map = {r[0]: r[1] for r in title_rows}
            cluster_results.append({
                "cluster_id": int(label),
                "note_ids": ids,
                "note_count": len(ids),
                "representative_title": title_map.get(ids[0], "Unknown"),
                "titles": [title_map.get(i, "Unknown") for i in ids[:5]],
            })

    # Sort by cluster size descending
    cluster_results.sort(key=lambda c: c["note_count"], reverse=True)

    return {
        "clusters": cluster_results,
        "total_notes": len(rows),
        "noise_count": int(sum(1 for l in labels if l == -1)),
    }


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
