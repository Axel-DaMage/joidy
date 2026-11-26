import logging
from typing import cast

import anthropic
import httpx2  # the anthropic SDK vendors this httpx fork; http_client requires it
from config import settings

from .base import BaseLLMClient
from .httpx_utils import build_async_http_client
from .retry import call_with_retry, is_transient_error

logger = logging.getLogger(__name__)


class AnthropicClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str):
        timeout = httpx2.Timeout(settings.llm_timeout, connect=settings.connect_timeout)
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key,
            timeout=timeout,
            # The SDK's own retry layer (default max_retries=2) stays off —
            # call_with_retry below is authoritative, otherwise every outer
            # attempt would multiply into up to 3 provider calls (#1620).
            max_retries=0,
            # trust_env=False so ambient HTTP(S)_PROXY vars are ignored unless
            # PROVIDER_PROXY_URL is explicitly configured (#1330). NOTE: a
            # plain httpx2.AsyncClient is used on purpose — the SDK's
            # DefaultAsyncHttpxClient reads env proxies itself and would mount
            # them even with trust_env=False.
            http_client=build_async_http_client(httpx2.AsyncClient, timeout),
        )
        self._model = model

    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError("Anthropic doesn't provide embeddings API")

    async def embed(self, text: str) -> list[float]:
        raise NotImplementedError("Anthropic doesn't provide embeddings API")

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 256,
        system_prompt: str | None = None,
    ) -> str:
        response = await call_with_retry(
            self._client.messages.create,
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
            is_retryable=_is_retryable_error,
            provider="Anthropic",
        )
        return cast("str", response.content[0].text)

    async def close(self) -> None:
        """Close the SDK's underlying httpx client (#998)."""
        await self._client.close()


def _is_retryable_error(exc: Exception) -> bool:
    """Shared transient coverage plus Anthropic's "overloaded" marker (#1540)."""
    return is_transient_error(exc) or "overloaded" in str(exc).lower()
