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

Reviewer-hardening on top of #1538 (#1628):

- *Health-error-only cooling*: only transient/provider-health failures
  (timeouts, connection errors, 408/429, 5xx — see ``_is_health_error``)
  arm the cooldown. A request-scoped error (4xx bad input, safety
  rejection) fails over for that one request but leaves the provider a
  normal candidate for the next — a single malformed prompt must not
  divert all traffic for a whole cooldown window.
- *Single-flight half-open probes*: when a cooldown expires, the first
  request to see it takes a per-provider *probe lease*; concurrent
  requests skip that provider until the lease resolves (success clears
  the cooldown, failure re-arms it, cancellation releases the lease via
  ``finally``). Without the lease every concurrent request would probe a
  recovering provider at once and each pay its dead-provider latency.
  Plain dicts/flags suffice — the event loop is single-threaded and the
  lease is taken/released between awaits.
- *Observation timestamps*: every recorded provider-health observation
  (traffic success/failure, health-check result) bumps
  ``last_observed_at`` so /health can compare signal freshness against
  the cached probe (#1628).
"""

import logging
import re
import time
from collections.abc import Iterable

from .base import BaseLLMClient, EmbeddingClient

logger = logging.getLogger(__name__)

# How long a failed provider is skipped before it is retried (#1538).
_PROVIDER_COOLDOWN_SECONDS = 60.0

# ``HTTP <3 digits>`` in a message — covers providers that only stringify
# the status (e.g. Ollama's error body).
_HTTP_STATUS_RE = re.compile(r"HTTP (\d{3})")

# Attribute names SDK exceptions use for the HTTP status: OpenAI/Anthropic
# ``status_code``, aiohttp ``status``, google-genai ``code`` (its ``status``
# is a string like "RESOURCE_EXHAUSTED" — the int guard skips it).
_STATUS_ATTRS = ("status_code", "status", "code")


def _status_is_transient(status: int) -> bool:
    """True when an HTTP status points at provider health, not request shape.

    408/429 (request timeout, rate limit) and every 5xx are transient or
    provider-side. Other 4xx describe *this request* (bad input, auth,
    safety) — another provider may still answer it, but the provider that
    returned it is not sick and must not be cooled (#1628).
    """
    return status in (408, 429) or status >= 500


def _is_health_error(exc: BaseException) -> bool:
    """Decide whether ``exc`` should cool the provider (#1628).

    Order of evidence:

    1. *Typed status attributes* on the exception —
       ``.status_code``/``.status``/``.code`` and httpx-style
       ``.response.status_code`` — restricted to plausible HTTP values
       (100-599) so non-HTTP numeric codes (e.g. gRPC status enums) don't
       misclassify.
    2. *Message parse* — ``HTTP <3 digits>`` inside ``str(exc)`` for
       providers that only stringify the status.
    3. *Default True* (transient) for exceptions carrying NO status: a
       bare timeout or connection error has no status and IS
       health-relevant, while anything carrying a 4xx was already
       classified above. Skipping the cooldown for a status-less failure
       would let a dead provider keep absorbing first-request latency —
       the worse failure mode, so uncertainty resolves to "cool".
    """
    for attr in _STATUS_ATTRS:
        value = getattr(exc, attr, None)
        if isinstance(value, int) and not isinstance(value, bool) and 100 <= value <= 599:
            return _status_is_transient(value)
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None) if response is not None else None
    if isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599:
        return _status_is_transient(status)
    match = _HTTP_STATUS_RE.search(str(exc))
    if match:
        return _status_is_transient(int(match.group(1)))
    return True


class FallbackLLMClient(BaseLLMClient):
    """Ordered failover chain for LLM calls.

    ``primary`` is tried first; on any exception each fallback in
    ``fallbacks`` is tried in order until one succeeds. If every provider
    fails, the *last* provider's exception propagates to the caller.

    Providers in cooldown (recently failed on a *health* error) are
    skipped so traffic goes straight to the healthy fallback (#1538).
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
        # Chain index → lease timestamp while a half-open probe is in flight
        # (#1628): only the request that took the lease tries the recovering
        # provider; concurrent requests skip it until the probe resolves.
        self._probe_leases: dict[int, float] = {}
        # Monotonic timestamp of the newest provider-health observation this
        # wrapper recorded — /health compares it against the probe-cache TTL.
        self.last_observed_at = 0.0

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

    def _candidate_indices(self, size: int) -> tuple[list[int], set[int]]:
        """Chain indices to try, in order, skipping cooled/probing providers.

        Returns ``(order, leased)`` where ``leased`` are the indices this
        call newly claimed as half-open probes; the caller MUST release them
        (``self._probe_leases.pop``) once done — a ``finally`` around the
        attempt loop covers returns, exceptions and cancellation.

        Half-open semantics (#1538): once a cooldown expires the provider is
        tried again in its normal position, and a fresh failure re-arms the
        cooldown. Single-flight (#1628): only the first request past an
        expired cooldown takes the probe lease — concurrent requests skip
        that index instead of each paying the dead provider's latency. When
        *every* provider is cooling or leased, cooled-but-unleased indices
        are tried, then the full chain as a last resort — paying failover
        latency beats returning a certain error.
        """
        now = time.monotonic()
        order: list[int] = []
        leased: set[int] = set()
        for i in range(size):
            down_until = self._down_until.get(i)
            if down_until is None:
                order.append(i)
                continue
            if down_until > now:
                continue  # actively cooling
            if i in self._probe_leases:
                continue  # another request is already probing it
            # Expired cooldown → this call becomes the single half-open probe.
            self._probe_leases[i] = now
            leased.add(i)
            order.append(i)
        if not order:
            order = [i for i in range(size) if i not in self._probe_leases] or list(range(size))
        return order, leased

    def _release_leases(self, leased: set[int]) -> None:
        for index in leased:
            self._probe_leases.pop(index, None)

    def _record_success(self, index: int) -> None:
        self._active_index = index
        self._down_until.pop(index, None)
        self._probe_leases.pop(index, None)
        self.last_observed_at = time.monotonic()

    def _record_failure(self, index: int, exc: BaseException) -> None:
        self._probe_leases.pop(index, None)
        self.last_observed_at = time.monotonic()
        # Only health/transient errors cool the provider — a request-scoped
        # 4xx must not divert all traffic for the cooldown window (#1628).
        if _is_health_error(exc):
            self._down_until[index] = self.last_observed_at + self._cooldown_seconds
        else:
            self._down_until.pop(index, None)

    async def embed_text(self, text: str) -> list[float]:
        clients = self.chain
        last_exc: Exception | None = None
        candidates, leased = self._candidate_indices(len(clients))
        try:
            for position, index in enumerate(candidates):
                client = clients[index]
                try:
                    result = await client.embed_text(text)
                    self._record_success(index)
                    return result
                except Exception as exc:
                    last_exc = exc
                    self._record_failure(index, exc)
                    self._log_fallback_step("embed_text", index, clients, exc, candidates, position)
        finally:
            # Release probes claimed by this call — covers success returns,
            # raised errors and task cancellation alike (#1628).
            self._release_leases(leased)
        # Chain is never empty — surface the LAST provider's error so the
        # caller sees a real failure, not a generic "primary failed" (#1460).
        raise last_exc or RuntimeError("all LLM providers failed")

    async def health_check(self) -> bool:
        """Healthy if any provider in the chain is reachable.

        Providers in cooldown are skipped — they are already known down, so
        probing them again would just burn a billable ping (#1538).
        """
        clients = self.chain
        candidates, leased = self._candidate_indices(len(clients))
        try:
            for index in candidates:
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
        finally:
            self._release_leases(leased)

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 256,
        system_prompt: str | None = None,
    ) -> str:
        clients = self.chain
        last_exc: Exception | None = None
        candidates, leased = self._candidate_indices(len(clients))
        try:
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
                    self._record_failure(index, exc)
                    self._log_fallback_step("generate", index, clients, exc, candidates, position)
        finally:
            # Release probes claimed by this call — covers success returns,
            # raised errors and task cancellation alike (#1628).
            self._release_leases(leased)
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
        # Single-flight half-open lease (#1628): while one request probes a
        # primary whose cooldown just expired, concurrent embeds keep going
        # straight to the secondary instead of each paying the probe latency.
        self._primary_probing = False
        # Monotonic timestamp of the newest provider-health observation —
        # /health compares it against the probe-cache TTL (#1628).
        self.last_observed_at = 0.0

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
        if self._primary_cooling() or self._primary_probing:
            # Known-down primary (or a half-open probe already in flight):
            # go straight to the secondary instead of paying the primary's
            # failure latency on every embed (#1538, #1628).
            self._using_fallback = True
            return await self._secondary.embed(text)
        # Cooldown expired → this coroutine is the single half-open probe.
        # The lease is only held for *recovering* primaries — a never-failed
        # primary keeps normal concurrency on healthy traffic (#1628).
        self._primary_probing = self._primary_down_until > 0.0
        try:
            result = await self._primary.embed(text)
            self._using_fallback = False
            self.last_observed_at = time.monotonic()
            return result
        except Exception as exc:
            self.last_observed_at = time.monotonic()
            logger.warning(
                f"Primary embedding provider '{self._primary.provider_name}' embed failed: {exc}. "
                f"Falling back to '{self._secondary.provider_name}'."
            )
            self._using_fallback = True
            # Only health/transient errors re-arm the cooldown — a
            # request-scoped error (4xx) fails over once, then the primary
            # is tried again normally (#1628).
            self._primary_down_until = self.last_observed_at + self._cooldown_seconds if _is_health_error(exc) else 0.0
            return await self._secondary.embed(text)
        finally:
            self._primary_probing = False

    async def health_check(self) -> bool:
        """Healthy if either primary or secondary is reachable.

        A cooling (or already-probing) primary is reported down without
        being probed — it is already known failing, so pinging it again
        would only burn a billable call (#1538, #1628).
        """
        primary_ok = False if (self._primary_cooling() or self._primary_probing) else await self._primary.health_check()
        if primary_ok:
            self._using_fallback = False
            self.last_observed_at = time.monotonic()
            return True
        secondary_ok = await self._secondary.health_check()
        self.last_observed_at = time.monotonic()
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
