import logging
from typing import cast

import cohere
import httpx
from config import settings

from .base import BaseLLMClient, EmbeddingClient
from .httpx_utils import build_async_http_client
from .retry import call_with_retry, is_transient_error

logger = logging.getLogger(__name__)


class CohereClient(BaseLLMClient, EmbeddingClient):
    def __init__(self, api_key: str, model: str, is_embedding: bool = False):
        timeout = settings.embed_timeout if is_embedding else settings.llm_timeout
        self._client = cohere.AsyncClient(
            api_key=api_key,
            timeout=timeout,
            # trust_env=False so ambient HTTP(S)_PROXY vars are ignored unless
            # PROVIDER_PROXY_URL is explicitly configured (#1330).
            httpx_client=build_async_http_client(
                httpx.AsyncClient,
                httpx.Timeout(timeout, connect=settings.connect_timeout),
            ),
        )
        self._model = model
        self._is_embedding = is_embedding

    @property
    def provider_name(self) -> str:
        return "cohere"

    async def embed_text(self, text: str) -> list[float]:
        return await self.embed(text)

    async def embed(self, text: str) -> list[float]:
        response = await call_with_retry(
            self._client.embed,
            texts=[text],
            model=self._model,
            is_retryable=_is_retryable_error,
            provider="Cohere",
        )
        return cast("list[float]", response.embeddings[0])

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 256,
        system_prompt: str | None = None,
    ) -> str:
        preamble = system_prompt or ""
        response = await call_with_retry(
            self._client.chat,
            message=prompt,
            preamble=preamble,
            temperature=temperature,
            max_tokens=max_tokens,
            model=self._model,
            is_retryable=_is_retryable_error,
            provider="Cohere",
        )
        return cast("str", response.text)

    async def close(self) -> None:
        """Close the SDK's underlying HTTP client if it exposes one (#998)."""
        close = getattr(self._client, "close", None)
        if close is not None:
            await close()


def _is_retryable_error(exc: Exception) -> bool:
    """Shared transient coverage (429/rate-limit, timeouts, 5xx) — #1540."""
    return is_transient_error(exc)
