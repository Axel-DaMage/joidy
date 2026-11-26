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

Failover is *sticky* (#1538): a provider that fails is skipped for
``_PROVIDER_COOLDOWN_SECONDS`` so a dead primary does not add its full
failure latency (and quota burn) to every request. Once the cooldown
expires the provider is tried again in its normal position — a half-open
probe — and a fresh failure re-arms the cooldown. State is in-memory only,
which is fine because the service runs as a single process.
"""

import logging
import time
from collections.abc import Iterable

from .base import BaseLLMClient, EmbeddingClient

logger = logging.getLogger(__name__)

# How long a failed provider is skipped before it is retried (#1538).
_PROVIDER_COOLDOWN_SECONDS = 60.0


class FallbackLLMClient(BaseLLMClient):
    """Ordered failover chain for LLM calls.

    ``primary`` is tried first; on any exception each fallback in
    ``fallbacks`` is tried in order until one succeeds. If every provider
    fails, the *last* provider's exception propagates to the caller.

    Providers in cooldown (recently failed) are skipped so traffic goes
    straight to the healthy fallback (#1538).
    """

    def __init__(
        self,
        primary: BaseLLMClient,
        fallbacks: Iterable[BaseLLMClient],
        cooldown_seconds: float = _PROVIDER_COOLDOWN_SECONDS,
    ):
        self._primary = primary
        self._fallbacks = list(fallbacks)
        self._active_index = 0
        self._cooldown_seconds = cooldown_seconds
        # Chain index → monotonic timestamp until which it is skipped (#1538).
        self._down_until: dict[int, float] = {}

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

    def _candidate_indices(self, size: int) -> list[int]:
        """Chain indices to try, in order, skipping providers in cooldown.

        Half-open semantics (#1538): once a cooldown expires the provider is
        tried again in its normal position, and a fresh failure re-arms the
        cooldown. When *every* provider is cooling the full chain is still
        tried — paying failover latency beats returning a certain error.
        """
        now = time.monotonic()
        order = [i for i in range(size) if self._down_until.get(i, 0.0) <= now]
        return order or list(range(size))

    def _record_success(self, index: int) -> None:
        self._active_index = index
        self._down_until.pop(index, None)

    def _record_failure(self, index: int) -> None:
        self._down_until[index] = time.monotonic() + self._cooldown_seconds

    async def embed_text(self, text: str) -> list[float]:
        clients = self.chain
        last_exc: Exception | None = None
        candidates = self._candidate_indices(len(clients))
        for position, index in enumerate(candidates):
            client = clients[index]
            try:
                result = await client.embed_text(text)
                self._record_success(index)
                return result
            except Exception as exc:
                last_exc = exc
                self._record_failure(index)
                self._log_fallback_step("embed_text", index, clients, exc, candidates, position)
        # Chain is never empty — surface the LAST provider's error so the
        # caller sees a real failure, not a generic "primary failed" (#1460).
        raise last_exc or RuntimeError("all LLM providers failed")

    async def health_check(self) -> bool:
        """Healthy if any provider in the chain is reachable.

        Providers in cooldown are skipped — they are already known down, so
        probing them again would just burn a billable ping (#1538).
        """
        clients = self.chain
        for index in self._candidate_indices(len(clients)):
            client = clients[index]
            if await client.health_check():
                self._record_success(index)
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
        candidates = self._candidate_indices(len(clients))
        for position, index in enumerate(candidates):
            client = clients[index]
            try:
                result = await client.generate(
                    prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=system_prompt,
                )
                self._record_success(index)
                return result
            except Exception as exc:
                last_exc = exc
                self._record_failure(index)
                self._log_fallback_step("generate", index, clients, exc, candidates, position)
        # Chain is never empty — surface the LAST provider's error so the
        # caller sees a real failure, not a generic "primary failed" (#1460).
        raise last_exc or RuntimeError("all LLM providers failed")

    def _log_fallback_step(
        self,
        op: str,
        index: int,
        clients: list[BaseLLMClient],
        exc: Exception,
        candidates: list[int],
        position: int,
    ) -> None:
        next_provider = clients[candidates[position + 1]].provider_name if position + 1 < len(candidates) else None
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

    def __init__(
        self,
        primary: EmbeddingClient,
        secondary: EmbeddingClient,
        cooldown_seconds: float = _PROVIDER_COOLDOWN_SECONDS,
    ):
        self._primary = primary
        self._secondary = secondary
        self._using_fallback = False
        self._cooldown_seconds = cooldown_seconds
        # Monotonic timestamp until which the primary is skipped (#1538).
        self._primary_down_until = 0.0

    @property
    def chain(self) -> list[EmbeddingClient]:
        """Both providers, primary first — for /health reachability detail (#1460)."""
        return [self._primary, self._secondary]

    @property
    def provider_name(self) -> str:
        return self._secondary.provider_name if self._using_fallback else self._primary.provider_name

    def _primary_cooling(self) -> bool:
        """True while the primary sits in its post-failure cooldown (#1538)."""
        return self._primary_down_until > time.monotonic()

    async def embed(self, text: str) -> list[float]:
        if self._primary_cooling():
            # Known-down primary: go straight to the secondary instead of
            # paying the primary's failure latency on every embed (#1538).
            self._using_fallback = True
            return await self._secondary.embed(text)
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
            self._primary_down_until = time.monotonic() + self._cooldown_seconds
            return await self._secondary.embed(text)

    async def health_check(self) -> bool:
        """Healthy if either primary or secondary is reachable.

        A cooling primary is reported down without being probed — it is
        already known failing, so pinging it again would only burn a
        billable call (#1538).
        """
        primary_ok = False if self._primary_cooling() else await self._primary.health_check()
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
