import logging
import struct
from collections.abc import AsyncIterator
from typing import cast

from config import settings
from google import genai
from google.genai import types

from .base import BaseLLMClient, EmbeddingClient
from .retry import call_with_retry, is_transient_error

logger = logging.getLogger(__name__)


class GeminiClient(BaseLLMClient, EmbeddingClient):
    """Gemini provider backed by the ``google-genai`` SDK (#1462).

    The legacy ``google.generativeai`` package is EOL upstream. ``google.genai``
    exposes a native async API (``client.aio.models``), so calls are awaited
    directly — no executor bridge — and ``asyncio.wait_for`` cancellation in
    the shared ``call_with_retry`` now actually aborts the in-flight HTTP
    request instead of orphaning a worker thread.
    """

    def __init__(self, api_key: str, model: str):
        # HttpOptions.timeout is in milliseconds; the asyncio.wait_for in
        # call_with_retry stays as a per-call backstop with its own budget.
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(max(settings.embed_timeout, settings.llm_timeout) * 1000)),
        )
        self._model = model

    @property
    def provider_name(self) -> str:
        return "gemini"

    async def embed_text(self, text: str) -> list[float]:
        return await self.embed(text)

    async def embed(self, text: str) -> list[float]:
        response = await call_with_retry(
            self._client.aio.models.embed_content,
            model=self._model,
            contents=text,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
            is_retryable=_is_retryable_error,
            timeout=settings.embed_timeout,
            provider="Gemini",
        )
        return cast("list[float]", list(response.embeddings[0].values))

    @staticmethod
    def _generation_config(
        temperature: float,
        max_tokens: int,
        system_prompt: str | None,
    ) -> types.GenerateContentConfig:
        """Build the request config, attaching the system instruction when one
        is provided (e.g. the chat/RAG grounding prompt, #1131).

        The new SDK has no ``GenerativeModel`` object — system instructions
        ride inside ``GenerateContentConfig`` per request (#1462).
        """
        return types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_prompt,
        )

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 256,
        system_prompt: str | None = None,
    ) -> str:
        response = await call_with_retry(
            self._client.aio.models.generate_content,
            model=self._model,
            contents=prompt,
            config=self._generation_config(temperature, max_tokens, system_prompt),
            is_retryable=_is_retryable_error,
            timeout=settings.llm_timeout,
            provider="Gemini",
        )
        return cast("str", response.text or "")

    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 256,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """Native async streaming via ``generate_content_stream`` (#1131/#1462).

        Stream *initiation* goes through ``call_with_retry`` so a dead or
        rate-limited provider fails fast and through the circuit breaker;
        mid-stream errors propagate to the consumer, which surfaces them as
        an SSE error frame.
        """
        stream = await call_with_retry(
            self._client.aio.models.generate_content_stream,
            model=self._model,
            contents=prompt,
            config=self._generation_config(temperature, max_tokens, system_prompt),
            is_retryable=_is_retryable_error,
            timeout=settings.llm_timeout,
            provider="Gemini",
        )
        async for chunk in stream:
            # chunk.text may raise on safety-blocked chunks.
            try:
                text = chunk.text or ""
            except ValueError:
                text = ""
            if text:
                yield text

    async def close(self) -> None:
        """Release the SDK's underlying async transport (#998/#1462)."""
        try:
            await self._client.aio.aclose()
        except Exception:  # close is best-effort — transport details vary
            logger.debug("Gemini client close failed", exc_info=True)


def _is_retryable_error(exc: Exception) -> bool:
    """Shared transient coverage plus Gemini's RESOURCE_EXHAUSTED marker (#1540)."""
    return is_transient_error(exc) or "resource exhausted" in str(exc).lower()


def embedding_to_bytes(embedding: list[float]) -> bytes:
    return struct.pack(f"{len(embedding)}f", *embedding)


def bytes_to_embedding(b: bytes) -> list[float]:
    n = len(b) // 4
    return list(struct.unpack(f"{n}f", b))
