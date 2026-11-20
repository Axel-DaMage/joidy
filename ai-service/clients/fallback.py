"""Failover-chain wrapper clients (#568, extended to N providers in #1460).

When the primary LLM/embedding provider (e.g. Gemini) is unavailable — API
key invalid, network error, quota exhausted — the wrapper transparently
retries the operation on each fallback provider in order.

Fallback order (defined by ``ClientFactory`` in ``factory.py``):
``LLM_MODEL`` provider → every other *configured* provider in
``_LLM_FALLBACK_ORDER`` order → Ollama always last, since it is the only
fully-local provider (no API key, no external dependency) and therefore
the final safety net. Previously the chain was ``primary → ollama`` only,
which ignored other configured providers entirely (#1460).
"""

import logging
from collections.abc import Iterable

from .base import BaseLLMClient, EmbeddingClient

logger = logging.getLogger(__name__)


class FallbackLLMClient(BaseLLMClient):
    """Ordered failover chain for LLM calls.

    ``primary`` is tried first; on any exception each fallback in
    ``fallbacks`` is tried in order until one succeeds. If every provider
    fails, the *last* provider's exception propagates to the caller.
    """

    def __init__(self, primary: BaseLLMClient, fallbacks: Iterable[BaseLLMClient]):
        self._primary = primary
        self._fallbacks = list(fallbacks)
        self._active_index = 0

    @property
    def chain(self) -> list[BaseLLMClient]:
        """The full provider chain, primary first.

        Exposed so /health can report per-provider reachability (#1460)
        without poking at private attributes.
        """
        return [self._primary, *self._fallbacks]

    @property
    def _active(self) -> BaseLLMClient:
        return self.chain[self._active_index]

    @property
    def provider_name(self) -> str:
        return self._active.provider_name

    async def embed_text(self, text: str) -> list[float]:
        clients = self.chain
        last_exc: Exception | None = None
        for index, client in enumerate(clients):
            try:
                result = await client.embed_text(text)
                self._active_index = index
                return result
            except Exception as exc:
                last_exc = exc
                self._log_fallback_step("embed_text", index, clients, exc)
        # Chain is never empty — surface the LAST provider's error so the
        # caller sees a real failure, not a generic "primary failed" (#1460).
        raise last_exc or RuntimeError("all LLM providers failed")

    async def health_check(self) -> bool:
        """Healthy if any provider in the chain is reachable."""
        for index, client in enumerate(self.chain):
            if await client.health_check():
                self._active_index = index
                if index > 0:
                    logger.warning(
                        f"Primary LLM provider '{self._primary.provider_name}' unhealthy. "
                        f"Using fallback '{client.provider_name}'."
                    )
                return True
        return False

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 256,
        system_prompt: str | None = None,
    ) -> str:
        clients = self.chain
        last_exc: Exception | None = None
        for index, client in enumerate(clients):
            try:
                result = await client.generate(
                    prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=system_prompt,
                )
                self._active_index = index
                return result
            except Exception as exc:
                last_exc = exc
                self._log_fallback_step("generate", index, clients, exc)
        # Chain is never empty — surface the LAST provider's error so the
        # caller sees a real failure, not a generic "primary failed" (#1460).
        raise last_exc or RuntimeError("all LLM providers failed")

    def _log_fallback_step(self, op: str, index: int, clients: list[BaseLLMClient], exc: Exception) -> None:
        next_provider = clients[index + 1].provider_name if index + 1 < len(clients) else None
        if next_provider:
            logger.warning(
                f"LLM provider '{clients[index].provider_name}' {op} failed: {exc}. Falling back to '{next_provider}'."
            )
        else:
            logger.exception(f"LLM provider '{clients[index].provider_name}' {op} failed — fallback chain exhausted")

    async def close(self) -> None:
        """Close every wrapped client (#998)."""
        for client in self.chain:
            await client.close()


class FallbackEmbeddingClient(EmbeddingClient):
    """Wraps a primary embedding client and falls back to a secondary on exception.

    Embeddings stay a two-provider chain (primary → secondary): cross-provider
    vectors have incompatible dimensions, so offering more embedding fallbacks
    would poison ``note_embeddings`` with mixed-dimensionality rows (#1460).
    """

    def __init__(self, primary: EmbeddingClient, secondary: EmbeddingClient):
        self._primary = primary
        self._secondary = secondary
        self._using_fallback = False

    @property
    def chain(self) -> list[EmbeddingClient]:
        """Both providers, primary first — for /health reachability detail (#1460)."""
        return [self._primary, self._secondary]

    @property
    def provider_name(self) -> str:
        return self._secondary.provider_name if self._using_fallback else self._primary.provider_name

    async def embed(self, text: str) -> list[float]:
        try:
            result = await self._primary.embed(text)
            self._using_fallback = False
            return result
        except Exception as exc:
            logger.warning(
                f"Primary embedding provider '{self._primary.provider_name}' embed failed: {exc}. "
                f"Falling back to '{self._secondary.provider_name}'."
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
                f"Primary embedding provider '{self._primary.provider_name}' unhealthy. "
                f"Using fallback '{self._secondary.provider_name}'."
            )
        return secondary_ok

    async def close(self) -> None:
        """Close both wrapped clients (#998)."""
        await self._primary.close()
        await self._secondary.close()
