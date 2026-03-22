"""
Thin wrapper around google-generativeai with rate limiting.
"""

import struct
from typing import Optional

import google.generativeai as genai

from config import settings
from rate_limiter import get_limiter


def _setup():
    if settings.gemini_api_key:
        genai.configure(api_key=settings.gemini_api_key)


_setup()


async def embed_text(text: str) -> list[float]:
    """Generate embedding vector for a piece of text."""
    limiter = get_limiter(settings.max_requests_per_minute)
    await limiter.acquire()

    result = genai.embed_content(
        model=settings.embedding_model,
        content=text,
        task_type="RETRIEVAL_DOCUMENT",
    )
    return result["embedding"]


async def classify_note(content: str, existing_tags: list[str]) -> list[dict]:
    """
    Returns a list of suggested tags with confidence scores.
    Each item: {"tag": str, "confidence": float, "is_new": bool}
    """
    limiter = get_limiter(settings.max_requests_per_minute)
    await limiter.acquire()

    tags_context = ", ".join(existing_tags) if existing_tags else "ninguno aún"
    prompt = _CLASSIFY_PROMPT.format(content=content[:2000], existing_tags=tags_context)

    model = genai.GenerativeModel(settings.llm_model)
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            temperature=0.2,
            max_output_tokens=256,
        ),
    )

    return _parse_classification(response.text, existing_tags)


async def rag_query(question: str, context_chunks: list[str]) -> str:
    """Answer a question using provided context chunks."""
    limiter = get_limiter(settings.max_requests_per_minute)
    await limiter.acquire()

    context = "\n\n---\n\n".join(context_chunks[:5])
    prompt = _RAG_PROMPT.format(question=question, context=context)

    model = genai.GenerativeModel(settings.llm_model)
    response = model.generate_content(prompt)
    return response.text


def embedding_to_bytes(embedding: list[float]) -> bytes:
    return struct.pack(f"{len(embedding)}f", *embedding)


def bytes_to_embedding(b: bytes) -> list[float]:
    n = len(b) // 4
    return list(struct.unpack(f"{n}f", b))


# ── Prompts ──────────────────────────────────────────────────────────────────

_CLASSIFY_PROMPT = """Eres un sistema de clasificación de notas de aprendizaje.
Analiza el siguiente contenido y sugiere tags (etiquetas) relevantes.

TAGS EXISTENTES EN EL SISTEMA: {existing_tags}

CONTENIDO DE LA NOTA:
{content}

INSTRUCCIONES:
- Sugiere entre 1 y 4 tags relevantes
- Prefiere tags existentes cuando sean aplicables
- Solo crea tags nuevos si el tema no está cubierto por los existentes
- Los tags deben ser cortos (1-3 palabras), en minúsculas, sin acentos
- Responde SOLO en este formato JSON, sin texto adicional:
[
  {{"tag": "nombre_tag", "confidence": 0.95, "is_new": false}},
  {{"tag": "otro_tag", "confidence": 0.7, "is_new": true}}
]"""

_RAG_PROMPT = """Eres un asistente personal de aprendizaje. Responde usando SOLO la información de las notas proporcionadas.
Si la respuesta no está en las notas, dilo claramente.

NOTAS RELEVANTES:
{context}

PREGUNTA: {question}

Responde de forma concisa y directa, citando conceptos de las notas cuando sea útil."""


def _parse_classification(text: str, existing_tags: list[str]) -> list[dict]:
    import json
    import re

    # Extract JSON array from response
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        suggestions = json.loads(match.group())
        result = []
        for s in suggestions:
            if isinstance(s, dict) and "tag" in s and "confidence" in s:
                result.append({
                    "tag": str(s["tag"]).lower().strip(),
                    "confidence": float(s.get("confidence", 0.5)),
                    "is_new": s.get("is_new", s["tag"] not in existing_tags),
                })
        return result
    except (json.JSONDecodeError, KeyError, ValueError):
        return []
