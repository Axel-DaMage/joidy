"""Fallback wrapper clients that try a primary provider and fall back to a secondary on failure.

This addresses #568: when the primary LLM/embedding provider (e.g. Gemini) is
unavailable — API key invalid, network error, quota exhausted — the wrapper
transparently retries the operation on a secondary provider (typically Ollama,
which runs locally and has no external dependencies).
"""

import logging

from .base import BaseLLMClient, EmbeddingClient

logger = logging.getLogger(__name__)


class FallbackLLMClient(BaseLLMClient):
    """Wraps a primary LLM client and falls back to a secondary on exception."""

    def __init__(self, primary: BaseLLMClient, secondary: BaseLLMClient):
        self._primary = primary
        self._secondary = secondary
        self._using_fallback = False

    @property
    def provider_name(self) -> str:
        return (
            self._secondary.provider_name
            if self._using_fallback
            else self._primary.provider_name
        )

    async def embed_text(self, text: str) -> list[float]:
        if not hasattr(self._primary, "embed_text"):
            return await self.embed(text)
        try:
            result = await self._primary.embed_text(text)
            self._using_fallback = False
            return result
        except Exception as exc:
            logger.warning(
                f"Primary LLM provider '{self._primary.provider_name}' embed_text failed: {exc}. Falling back to '{self._secondary.provider_name}'."
            )
            self._using_fallback = True
            return await self._secondary.embed_text(text)

    async def health_check(self) -> bool:
        """Healthy if either primary or secondary is reachable."""
        primary_ok = await self._primary.health_check()
        if primary_ok:
            self._using_fallback = False
            return True
        secondary_ok = await self._secondary.health_check()
        if secondary_ok:
            self._using_fallback = True
            logger.warning(
                f"Primary LLM provider '{self._primary.provider_name}' unhealthy. Using fallback '{self._secondary.provider_name}'."
            )
        return secondary_ok

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 256,
        system_prompt: str | None = None,
    ) -> str:
        try:
            result = await self._primary.generate(
                prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                system_prompt=system_prompt,
            )
            self._using_fallback = False
            return result
        except Exception as exc:
            logger.warning(
                f"Primary LLM provider '{self._primary.provider_name}' generate failed: {exc}. Falling back to '{self._secondary.provider_name}'."
            )
            self._using_fallback = True
            return await self._secondary.generate(
                prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                system_prompt=system_prompt,
            )


class FallbackEmbeddingClient(EmbeddingClient):
    """Wraps a primary embedding client and falls back to a secondary on exception."""

    def __init__(self, primary: EmbeddingClient, secondary: EmbeddingClient):
        self._primary = primary
        self._secondary = secondary
        self._using_fallback = False

    @property
    def provider_name(self) -> str:
        return (
            self._secondary.provider_name
            if self._using_fallback
            else self._primary.provider_name
        )

    async def embed(self, text: str) -> list[float]:
        try:
            result = await self._primary.embed(text)
            self._using_fallback = False
            return result
        except Exception as exc:
            logger.warning(
                f"Primary embedding provider '{self._primary.provider_name}' embed failed: {exc}. Falling back to '{self._secondary.provider_name}'."
            )
            self._using_fallback = True
            return await self._secondary.embed(text)

    async def health_check(self) -> bool:
        """Healthy if either primary or secondary is reachable."""
        primary_ok = await self._primary.health_check()
        if primary_ok:
            self._using_fallback = False
            return True
        secondary_ok = await self._secondary.health_check()
        if secondary_ok:
            self._using_fallback = True
            logger.warning(
                f"Primary embedding provider '{self._primary.provider_name}' unhealthy. Using fallback '{self._secondary.provider_name}'."
            )
        return secondary_ok
