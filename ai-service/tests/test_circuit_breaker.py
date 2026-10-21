"""Unit tests for circuit_breaker.CircuitBreaker state transitions."""

import time
import unittest

from circuit_breaker import CircuitBreaker, CircuitBreakerError, CircuitState


async def _ok():
    return "ok"


async def _boom():
    raise RuntimeError("provider exploded")


class TestCircuitBreaker(unittest.IsolatedAsyncioTestCase):
    async def test_success_keeps_circuit_closed(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)
        result = await cb.call(_ok)
        self.assertEqual(result, "ok")
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertEqual(cb.failures, 0)

    async def test_failures_below_threshold_stay_closed(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)
        for _ in range(2):
            with self.assertRaises(RuntimeError):
                await cb.call(_boom)
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertEqual(cb.failures, 2)

    async def test_threshold_reached_opens_circuit(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)
        for _ in range(3):
            with self.assertRaises(RuntimeError):
                await cb.call(_boom)
        self.assertEqual(cb.state, CircuitState.OPEN)

    async def test_open_circuit_fails_fast(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        with self.assertRaises(RuntimeError):
            await cb.call(_boom)
        self.assertEqual(cb.state, CircuitState.OPEN)

        called = False

        async def _should_not_run():
            nonlocal called
            called = True

        with self.assertRaises(CircuitBreakerError):
            await cb.call(_should_not_run)
        self.assertFalse(called)

    async def test_open_to_half_open_after_recovery_timeout(self):
        # recovery_timeout=0 means the next call immediately probes (HALF_OPEN).
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.0)
        with self.assertRaises(RuntimeError):
            await cb.call(_boom)
        self.assertEqual(cb.state, CircuitState.OPEN)

        result = await cb.call(_ok)
        self.assertEqual(result, "ok")
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertEqual(cb.failures, 0)

    async def test_half_open_failure_reopens_circuit(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.0)
        cb.state = CircuitState.OPEN
        cb.last_failure_time = time.time() - 1

        with self.assertRaises(RuntimeError):
            await cb.call(_boom)
        # A failure while probing sends the breaker straight back to OPEN even
        # though the cumulative failure threshold was already exceeded.
        self.assertEqual(cb.state, CircuitState.OPEN)

    async def test_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0)
        with self.assertRaises(RuntimeError):
            await cb.call(_boom)
        self.assertEqual(cb.failures, 1)

        cb.state = CircuitState.HALF_OPEN
        await cb.call(_ok)
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertEqual(cb.failures, 0)


if __name__ == "__main__":
    unittest.main()
