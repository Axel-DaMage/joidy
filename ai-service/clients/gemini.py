import asyncio
import logging
import struct
from collections.abc import AsyncIterator
from typing import cast

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
            ),
            timeout=settings.embed_timeout,
        )
        return cast("list[float]", result["embedding"])

    def _build_model(self, system_prompt: str | None):
        """Build the GenerativeModel, attaching the system instruction when
        one is provided (e.g. the chat/RAG grounding prompt, #1131)."""
        if system_prompt:
            return genai.GenerativeModel(self._model, system_instruction=system_prompt)
        return genai.GenerativeModel(self._model)

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 256,
        system_prompt: str | None = None,
    ) -> str:
        model = self._build_model(system_prompt)
        response = await _call_with_retry(
            lambda: model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            ),
            timeout=settings.llm_timeout,
        )
        return cast("str", response.text)

    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 256,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """True streaming via ``generate_content(stream=True)`` (#1131).

        The google-generativeai SDK is synchronous, so the blocking iterator
        runs in an executor thread that pushes chunks into an asyncio.Queue;
        the async generator drains the queue so FastAPI can forward tokens to
        the client as they arrive.
        """
        model = self._build_model(system_prompt)
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue[str | BaseException | None] = asyncio.Queue()

        def _worker() -> None:
            try:
                response = model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                    ),
                    stream=True,
                )
                for chunk in response:
                    # chunk.text raises ValueError on safety-blocked chunks.
                    try:
                        text = chunk.text or ""
                    except ValueError:
                        text = ""
                    if text:
                        loop.call_soon_threadsafe(queue.put_nowait, text)
            except Exception as exc:  # surfaced to the consumer below
                loop.call_soon_threadsafe(queue.put_nowait, exc)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        loop.run_in_executor(None, _worker)
        while True:
            item = await asyncio.wait_for(queue.get(), timeout=settings.llm_timeout)
            if item is None:
                return
            if isinstance(item, BaseException):
                raise item
            yield item


def _is_retryable_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "resource exhausted" in msg or "rate limit" in msg


async def _call_with_retry(func, timeout: float | None = None):
    attempts = max(1, settings.ai_retry_max_attempts)
    base = max(0.1, settings.ai_retry_base_delay_seconds)
    cap = max(base, settings.ai_retry_max_delay_seconds)

    for attempt in range(1, attempts + 1):
        try:
            # Run the synchronous google.generativeai call in a thread to
            # avoid blocking the FastAPI event loop. google-generativeai does
            # not expose a per-request timeout, so enforce one with wait_for.
            loop = asyncio.get_event_loop()
            coro = loop.run_in_executor(None, func)
            if timeout is not None:
                return await asyncio.wait_for(coro, timeout=timeout)
            return await coro
        except TimeoutError:
            raise TimeoutError(f"Gemini call timed out after {timeout}s")
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
