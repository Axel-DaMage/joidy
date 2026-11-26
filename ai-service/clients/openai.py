import logging
from collections.abc import AsyncIterator
from typing import cast

import httpx2  # the openai SDK vendors this httpx fork; its transport requires it
from config import settings, validate_base_url
from openai import AsyncOpenAI, DefaultAsyncHttpx2Client

from .base import BaseLLMClient, EmbeddingClient
from .httpx_utils import build_async_http_client
from .retry import call_with_retry, is_transient_error

logger = logging.getLogger(__name__)


class OpenAIClient(BaseLLMClient, EmbeddingClient):
    def __init__(self, api_key: str, model: str, is_embedding: bool = False, base_url: str = ""):
        if base_url:
            # Custom OpenAI-compatible routers must use https:// unless they
            # point at loopback — a cleartext remote base_url would send note
            # content and the api_key to an arbitrary host (#1330).
            base_url = validate_base_url(
                base_url, name="OPENAI_BASE_URL", allow_insecure=settings.allow_insecure_base_urls
            )
        timeout = httpx2.Timeout(
            settings.embed_timeout if is_embedding else settings.llm_timeout,
            connect=settings.connect_timeout,
        )
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url or None,
            timeout=timeout,
            # The SDK's own retry layer (default max_retries=2) stays off —
            # call_with_retry below is authoritative, otherwise every outer
            # attempt would multiply into up to 3 provider calls (#1620).
            max_retries=0,
            # trust_env=False so ambient HTTP(S)_PROXY vars are ignored unless
            # PROVIDER_PROXY_URL is explicitly configured (#1330).
            http_client=build_async_http_client(DefaultAsyncHttpx2Client, timeout),
        )
        self._model = model
        self._is_embedding = is_embedding

    @property
    def provider_name(self) -> str:
        return "openai"

    async def embed_text(self, text: str) -> list[float]:
        return await self.embed(text)

    async def embed(self, text: str) -> list[float]:
        response = await call_with_retry(
            self._client.embeddings.create,
            model=self._model,
            input=text,
            is_retryable=_is_retryable_error,
            provider="OpenAI",
        )
        return cast("list[float]", response.data[0].embedding)

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 256,
        system_prompt: str | None = None,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Reasoning routers (e.g. "standardcompute") spend max_tokens on hidden
        # reasoning before emitting visible content — raise the floor if set.
        if settings.llm_max_tokens and settings.llm_max_tokens > max_tokens:
            max_tokens = settings.llm_max_tokens

        response = await call_with_retry(
            self._client.chat.completions.create,
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            is_retryable=_is_retryable_error,
            provider="OpenAI",
        )
        # finish_reason=length on reasoning models can leave content null.
        return response.choices[0].message.content or ""

    async def generate_stream(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 256,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """True streaming via ``chat.completions.create(stream=True)`` (#1131)."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        if settings.llm_max_tokens and settings.llm_max_tokens > max_tokens:
            max_tokens = settings.llm_max_tokens

        stream = await call_with_retry(
            self._client.chat.completions.create,
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            is_retryable=_is_retryable_error,
            provider="OpenAI",
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def close(self) -> None:
        """Close the SDK's underlying httpx client (#998)."""
        await self._client.close()


def _is_retryable_error(exc: Exception) -> bool:
    """Shared transient coverage (429/rate-limit, timeouts, 5xx) — #1540."""
    return is_transient_error(exc)
