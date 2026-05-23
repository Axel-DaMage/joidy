import asyncio
import logging
from typing import Optional

import cohere

from .base import BaseLLMClient, EmbeddingClient
from config import settings

logger = logging.getLogger(__name__)


class CohereClient(BaseLLMClient, EmbeddingClient):
    def __init__(self, api_key: str, model: str, is_embedding: bool = False):
        self._client = cohere.AsyncClient(api_key=api_key)
        self._model = model
        self._is_embedding = is_embedding

    @property
    def provider_name(self) -> str:
        return "cohere"

    async def embed_text(self, text: str) -> list[float]:
        return await self.embed(text)

    async def embed(self, text: str) -> list[float]:
        response = await _call_with_retry(
            self._client.embed,
            texts=[text],
            model=self._model,
        )
        return response.embeddings[0]

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 256,
        system_prompt: Optional[str] = None,
    ) -> str:
        preamble = system_prompt or ""
        response = await _call_with_retry(
            self._client.chat,
            message=prompt,
            preamble=preamble,
            temperature=temperature,
            max_tokens=max_tokens,
            model=self._model,
        )
        return response.text

    async def classify(
        self,
        content: str,
        existing_tags: list[str],
        classify_prompt: str,
    ) -> list[dict]:
        prompt = classify_prompt.format(
            content=content[:2000],
            existing_tags=", ".join(existing_tags) if existing_tags else "ninguno aún"
        )
        result = await self.generate(prompt, temperature=0.2, max_tokens=256)
        return _parse_classification(result, existing_tags)


def _is_retryable_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "rate_limit" in msg


async def _call_with_retry(func, *args, **kwargs):
    attempts = max(1, settings.ai_retry_max_attempts)
    base = max(0.1, settings.ai_retry_base_delay_seconds)
    cap = max(base, settings.ai_retry_max_delay_seconds)

    for attempt in range(1, attempts + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            if not _is_retryable_error(exc) or attempt >= attempts:
                raise
            delay = min(cap, base * (2 ** (attempt - 1)))
            logger.warning(f"Cohere call failed. attempt={attempt}/{attempts} delay={delay:.2f}s error={exc}")
            await asyncio.sleep(delay)


def _parse_classification(text: str, existing_tags: list[str]) -> list[dict]:
    import json
    import re

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