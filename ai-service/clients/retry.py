"""Shared retry helper for provider clients (#1540).

Unifies the ``_call_with_retry``/``_is_retryable_error`` helpers that were
copy-pasted across the gemini/openai/anthropic/cohere clients, and extends
the same policy to ollama/openrouter:

- Exponential backoff now applies *full jitter* (``random.uniform(0, delay)``,
  the AWS-recommended decorrelation strategy) so concurrent requests that hit
  a 429 together stop retrying in lockstep — synchronized retries are a
  thundering herd that amplifies rate-limit pressure exactly when the
  provider is already saturated.
- Timeouts, connection errors and 5xx responses are retryable in addition to
  rate limits — generate/embed calls are idempotent reads, so retrying them
  is safe.
- Each provider supplies its own ``is_retryable`` predicate (default:
  :func:`is_transient_error`) so provider-specific transient markers keep
  working.
"""

import asyncio
import logging
import random
import re
from collections.abc import Awaitable, Callable
from typing import Any

from config import settings

logger = logging.getLogger(__name__)

# Status-code attributes on the different SDK error types: openai/anthropic
# ``APIStatusError.status_code``, aiohttp ``ClientResponseError.status``,
# google-genai ``APIError.code``.
_STATUS_ATTRS = ("status_code", "status", "code")

# The aiohttp-based clients (ollama/openrouter) raise untyped ``Exception``s
# but embed the status as ``(HTTP NNN)`` in the message — parseable so a
# permanent 4xx never reaches the substring fallback below (#1620).
_HTTP_STATUS_RE = re.compile(r"HTTP (\d{3})")

# Last-resort substring markers for errors that expose no typed or parseable
# status — e.g. provider SDKs that only raise a plain message.
_TRANSIENT_MARKERS = (
    "429",
    "rate limit",
    "rate_limit",
    "too many requests",
    "500",
    "502",
    "503",
    "504",
    "internal server error",
    "bad gateway",
    "service unavailable",
    "gateway timeout",
    "timeout",
    "timed out",
    "connection",
)


def http_status(exc: BaseException) -> int | None:
    """Best-effort HTTP status extraction across SDK error shapes."""
    for attr in _STATUS_ATTRS:
        value = getattr(exc, attr, None)
        # Exclude bool, which is an int subclass.
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def is_transient_error(exc: Exception) -> bool:
    """Default retryable predicate: timeouts, connection failures, 429, 5xx.

    ``OSError`` covers the transient-transport family — builtin
    ``TimeoutError``/``ConnectionError``, ``asyncio.TimeoutError`` (the same
    builtin on Python 3.11+), and aiohttp's ``ClientOSError``/
    ``ClientConnectorError``. A typed status, when present, takes precedence
    over message matching so a 4xx can't be retried by accident; an
    ``HTTP NNN`` status embedded in the message is classified the same way
    before the substring fallback runs. Providers extend this with their own
    transient markers where needed.
    """
    if isinstance(exc, OSError):
        return True
    status = http_status(exc)
    if status is None:
        match = _HTTP_STATUS_RE.search(str(exc))
        if match:
            status = int(match.group(1))
    if status is not None:
        return status == 429 or status >= 500
    msg = str(exc).lower()
    return any(marker in msg for marker in _TRANSIENT_MARKERS)


async def call_with_retry(
    func: Callable[..., Awaitable[Any]],
    *args: Any,
    is_retryable: Callable[[Exception], bool] = is_transient_error,
    timeout: float | None = None,
    provider: str = "Provider",
    **kwargs: Any,
) -> Any:
    """Await ``func(*args, **kwargs)`` with backoff + full-jitter retries.

    ``func`` is invoked once per attempt and must return a *fresh* awaitable
    each time — a coroutine cancelled by ``wait_for`` cannot be re-awaited.

    Keyword-only parameters (reserved — do not pass an SDK kwarg with these
    names):

    - ``is_retryable``: predicate deciding whether a failure is retried.
    - ``timeout``: optional per-attempt ``asyncio.wait_for`` budget. A
      timed-out call is itself retryable and surfaces as a descriptive
      ``TimeoutError`` once attempts are exhausted. NOTE: a timed-out
      generation request may already have been billed by the provider —
      retrying it anyway is an intentional reliability trade-off;
      ``ai_retry_max_attempts`` caps the amplification (#1620).
    - ``provider``: label used in logs and the timeout message.

    Returns ``Any``: provider SDK response types flow opaquely through the
    forwarded call — callers ``cast()`` at the boundary, exactly as the
    per-client helpers did before.
    """
    attempts = max(1, settings.ai_retry_max_attempts)
    base = max(0.1, settings.ai_retry_base_delay_seconds)
    cap = max(base, settings.ai_retry_max_delay_seconds)

    for attempt in range(1, attempts + 1):
        try:
            awaitable = func(*args, **kwargs)
            if timeout is not None:
                return await asyncio.wait_for(awaitable, timeout=timeout)
            return await awaitable
        except Exception as exc:
            if not is_retryable(exc) or attempt >= attempts:
                if isinstance(exc, TimeoutError) and timeout is not None:
                    raise TimeoutError(f"{provider} call timed out after {timeout}s") from exc
                raise
            # Full jitter: uniform sample in [0, backoff] decorrelates
            # concurrent retries better than deterministic or equal-jitter
            # delays (#1540).
            delay = random.uniform(  # noqa: S311 -- backoff jitter needs speed, not a CSPRNG
                0, min(cap, base * (2 ** (attempt - 1)))
            )
            logger.warning(
                f"{provider} call failed; retrying. attempt={attempt}/{attempts} delay={delay:.2f}s error={exc}"
            )
            await asyncio.sleep(delay)
    raise AssertionError("unreachable: the retry loop always returns or raises")
