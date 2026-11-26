"""Unit tests for the shared provider retry helper (#1540).

Covers ``call_with_retry`` (full-jitter bounds, backoff cap, retryable vs
non-retryable, timeout handling, custom predicates) and
``is_transient_error`` (typed status extraction, timeouts/connection
errors, message markers).
"""

import unittest
from unittest.mock import AsyncMock, patch

from config import settings


def _fast_retry(**overrides):
    """Context manager patching retry knobs to near-instant values."""
    knobs = {"ai_retry_max_attempts": 3, "ai_retry_base_delay_seconds": 0.1, "ai_retry_max_delay_seconds": 30.0}
    knobs.update(overrides)
    return patch.multiple(settings, **knobs)


def _status_error(status, **attrs):
    exc = Exception("request failed")
    for name, value in {**attrs, "status_code": status}.items():
        setattr(exc, name, value)
    return exc


class _FlakyError(Exception):
    """Transient-looking provider failure used by the retry tests."""


class TestIsTransientError(unittest.TestCase):
    def test_timeout_error_is_transient(self):
        from clients.retry import is_transient_error

        self.assertTrue(is_transient_error(TimeoutError("timed out")))

    def test_connection_error_is_transient(self):
        from clients.retry import is_transient_error

        self.assertTrue(is_transient_error(ConnectionError("refused")))

    def test_oserror_is_transient(self):
        """aiohttp ClientConnectorError is OSError-based — covered here."""
        from clients.retry import is_transient_error

        self.assertTrue(is_transient_error(OSError("network unreachable")))

    def test_status_code_429_is_transient(self):
        from clients.retry import is_transient_error

        self.assertTrue(is_transient_error(_status_error(429)))

    def test_status_code_5xx_is_transient(self):
        from clients.retry import is_transient_error

        for status in (500, 502, 503, 504, 599):
            self.assertTrue(is_transient_error(_status_error(status)), f"status={status}")

    def test_status_code_4xx_is_not_transient(self):
        from clients.retry import is_transient_error

        for status in (400, 401, 403, 404, 422):
            self.assertFalse(is_transient_error(_status_error(status)), f"status={status}")

    def test_typed_status_beats_message(self):
        """A typed 4xx is permanent even if the message smells transient."""
        from clients.retry import is_transient_error

        exc = Exception("429 would be a lie")
        exc.status_code = 400
        self.assertFalse(is_transient_error(exc))

    def test_status_attr_aiohttp_style(self):
        from clients.retry import is_transient_error

        exc = Exception("boom")
        exc.status = 503
        self.assertTrue(is_transient_error(exc))

    def test_code_attr_google_genai_style(self):
        from clients.retry import is_transient_error

        exc = Exception("RESOURCE_EXHAUSTED")
        exc.code = 429
        self.assertTrue(is_transient_error(exc))

    def test_message_markers(self):
        from clients.retry import is_transient_error

        for msg in (
            "HTTP 429 too many requests",
            "rate limit hit",
            "rate_limit_exceeded",
            "503 Service Unavailable",
            "internal server error",
            "bad gateway",
            "gateway timeout",
            "Connection error.",
        ):
            self.assertTrue(is_transient_error(Exception(msg)), f"msg={msg!r}")

    def test_non_transient_messages(self):
        from clients.retry import is_transient_error

        for msg in ("invalid api key", "model not found", "bad request body"):
            self.assertFalse(is_transient_error(Exception(msg)), f"msg={msg!r}")


class TestCallWithRetry(unittest.IsolatedAsyncioTestCase):
    async def test_returns_on_first_success(self):
        from clients.retry import call_with_retry

        func = AsyncMock(return_value="ok")
        result = await call_with_retry(func)
        self.assertEqual(result, "ok")
        func.assert_called_once_with()

    async def test_retries_then_succeeds(self):
        from clients.retry import call_with_retry

        calls = []

        async def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise _FlakyError("429 rate limit")
            return "recovered"

        with _fast_retry():
            result = await call_with_retry(flaky)
        self.assertEqual(result, "recovered")
        self.assertEqual(len(calls), 3)

    async def test_fresh_awaitable_per_attempt(self):
        """func is re-invoked each retry (coroutines can't be re-awaited)."""
        from clients.retry import call_with_retry

        func = AsyncMock(side_effect=[_FlakyError("429"), "ok"])
        with _fast_retry():
            self.assertEqual(await call_with_retry(func), "ok")
        self.assertEqual(func.call_count, 2)

    async def test_non_retryable_raises_immediately(self):
        from clients.retry import call_with_retry

        calls = []

        async def bad_key():
            calls.append(1)
            raise RuntimeError("invalid api key")

        with _fast_retry(), self.assertRaises(RuntimeError):
            await call_with_retry(bad_key)
        self.assertEqual(len(calls), 1)

    async def test_exhaustion_raises_last_error(self):
        from clients.retry import call_with_retry

        async def always_limited():
            raise _FlakyError("429 rate limit")

        with _fast_retry(), self.assertRaises(_FlakyError) as ctx:
            await call_with_retry(always_limited)
        self.assertIn("429", str(ctx.exception))

    async def test_custom_predicate(self):
        from clients.retry import call_with_retry

        calls = []

        async def custom_transient():
            calls.append(1)
            raise RuntimeError("flaky-but-mine")

        with _fast_retry(), self.assertRaises(RuntimeError):
            await call_with_retry(custom_transient, is_retryable=lambda e: "flaky" in str(e))
        self.assertEqual(len(calls), 3)

    async def test_custom_predicate_blocks_default_transients(self):
        from clients.retry import call_with_retry

        calls = []

        async def limited():
            calls.append(1)
            raise _FlakyError("429")

        # Predicate that refuses everything — even a 429 fails fast.
        with _fast_retry(), self.assertRaises(_FlakyError):
            await call_with_retry(limited, is_retryable=lambda e: False)
        self.assertEqual(len(calls), 1)

    async def test_timeout_retried_then_descriptive_error(self):
        import asyncio

        from clients.retry import call_with_retry

        calls = []

        async def slow():
            calls.append(1)
            await asyncio.sleep(0.5)

        with _fast_retry(), self.assertRaises(TimeoutError) as ctx:
            await call_with_retry(slow, timeout=0.05, provider="TestProvider")
        self.assertIn("TestProvider call timed out after 0.05s", str(ctx.exception))
        self.assertEqual(len(calls), 3)

    async def test_timeout_recovers_when_later_attempt_is_fast(self):
        import asyncio

        from clients.retry import call_with_retry

        calls = []

        async def improving():
            calls.append(1)
            if len(calls) == 1:
                await asyncio.sleep(0.5)
            return "ok"

        with _fast_retry():
            result = await call_with_retry(improving, timeout=0.05)
        self.assertEqual(result, "ok")
        self.assertEqual(len(calls), 2)

    async def test_jitter_stays_within_backoff_bounds(self):
        """Every sleep lands in [0, min(cap, base * 2**(attempt-1))]."""
        from clients.retry import call_with_retry

        delays = []

        async def fake_sleep(delay):
            delays.append(delay)

        async def always_503():
            raise _FlakyError("503 service unavailable")

        with _fast_retry(), patch("asyncio.sleep", fake_sleep), self.assertRaises(_FlakyError):
            await call_with_retry(always_503)

        # 3 attempts → sleeps after attempts 1 and 2; caps 0.1 and 0.2.
        self.assertEqual(len(delays), 2)
        self.assertGreaterEqual(delays[0], 0)
        self.assertLessEqual(delays[0], 0.1)
        self.assertGreaterEqual(delays[1], 0)
        self.assertLessEqual(delays[1], 0.2)

    async def test_full_jitter_draws_uniform_from_zero(self):
        """Full jitter = random.uniform(0, backoff) — decorrelates retries."""
        from clients.retry import call_with_retry

        async def always_limited():
            raise _FlakyError("429")

        with _fast_retry(), patch("clients.retry.random.uniform", return_value=0.01) as mock_uniform:
            with self.assertRaises(_FlakyError):
                await call_with_retry(always_limited)
        mock_uniform.assert_any_call(0, 0.1)
        mock_uniform.assert_any_call(0, 0.2)

    async def test_backoff_respects_cap(self):
        from clients.retry import call_with_retry

        delays = []

        async def fake_sleep(delay):
            delays.append(delay)

        async def always_limited():
            raise _FlakyError("429")

        knobs = _fast_retry(
            ai_retry_max_attempts=4,
            ai_retry_base_delay_seconds=0.5,
            ai_retry_max_delay_seconds=0.6,
        )
        with knobs, patch("asyncio.sleep", fake_sleep), self.assertRaises(_FlakyError):
            await call_with_retry(always_limited)

        # Unclamped backoff would be 0.5, 1.0, 2.0 — the cap clamps to 0.6.
        self.assertEqual(len(delays), 3)
        for delay in delays:
            self.assertLessEqual(delay, 0.6)
        self.assertLessEqual(delays[0], 0.5)


if __name__ == "__main__":
    unittest.main()
