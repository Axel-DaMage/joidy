import asyncio
import logging
import struct

import google.generativeai as genai
from config import settings

from .base import BaseLLMClient, EmbeddingClient

logger = logging.getLogger(__name__)


class GeminiClient(BaseLLMClient, EmbeddingClient):
    def __init__(self, api_key: str, model: str):
        genai.configure(api_key=api_key)
        self._model = model

    @property
    def provider_name(self) -> str:
        return "gemini"

    async def embed_text(self, text: str) -> list[float]:
        return await self.embed(text)

    async def embed(self, text: str) -> list[float]:
        result = await _call_with_retry(
            lambda: genai.embed_content(
                model=self._model,
                content=text,
                task_type="RETRIEVAL_DOCUMENT",
            )
        )
        return result["embedding"]

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 256,
        system_prompt: str | None = None,
    ) -> str:
        model = genai.GenerativeModel(self._model)
        response = await _call_with_retry(
            lambda: model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )
        )
        return response.text


def _is_retryable_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "resource exhausted" in msg or "rate limit" in msg


async def _call_with_retry(func):
    attempts = max(1, settings.ai_retry_max_attempts)
    base = max(0.1, settings.ai_retry_base_delay_seconds)
    cap = max(base, settings.ai_retry_max_delay_seconds)

    for attempt in range(1, attempts + 1):
        try:
            return func()
        except Exception as exc:
            if not _is_retryable_error(exc) or attempt >= attempts:
                raise
            delay = min(cap, base * (2 ** (attempt - 1)))
            logger.warning(f"Gemini call rate-limited. attempt={attempt}/{attempts} delay={delay:.2f}s")
            await asyncio.sleep(delay)



def embedding_to_bytes(embedding: list[float]) -> bytes:
    return struct.pack(f"{len(embedding)}f", *embedding)


def bytes_to_embedding(b: bytes) -> list[float]:
    n = len(b) // 4
    return list(struct.unpack(f"{n}f", b))
