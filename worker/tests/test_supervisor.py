"""Tests for the worker task supervisor restart logic (#815).

Verifies that ``_supervise`` restarts a crashed task with exponential
backoff up to ``MAX_RESTARTS`` times, then surfaces the final crash via
``mark_crashed`` so ``/health`` reports degraded. Also checks that a clean
exit is not restarted and that ``CancelledError`` propagates.
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import main as worker_main
import task_status
from main import (
    INITIAL_BACKOFF,
    MAX_BACKOFF,
    MAX_RESTARTS,
    _supervise,
)


def _sleep_stub(delay):
    """Replace ``asyncio.sleep`` with a no-op so tests don't actually wait."""
    fut = asyncio.Future()
    fut.set_result(None)
    return fut


class SupervisorTest(unittest.TestCase):
    def setUp(self):
        # Reset the shared task-status registry between tests.
        with task_status._lock:
            task_status._tasks.clear()

    def test_clean_exit_is_not_restarted(self):
        calls = []

        async def factory():
            calls.append(1)

        asyncio.run(_supervise("t", factory))
        self.assertEqual(len(calls), 1)
        # Clean exit does not mark crashed.
        snap = task_status.snapshot()
        if "t" in snap:
            self.assertNotEqual(snap["t"]["state"], "crashed")

    def test_restarts_up_to_max_then_marks_crashed(self):
        attempts = []

        async def factory():
            attempts.append(1)
            raise RuntimeError("boom")

        with patch.object(worker_main.asyncio, "sleep", side_effect=_sleep_stub):
            asyncio.run(_supervise("t", factory))

        # MAX_RESTARTS retries + 1 initial attempt.
        self.assertEqual(len(attempts), MAX_RESTARTS + 1)
        snap = task_status.snapshot()
        self.assertIn("t", snap)
        self.assertEqual(snap["t"]["state"], "crashed")

    def test_recovers_after_transient_failure(self):
        """A crash followed by success should not mark the task crashed."""
        attempts = []

        async def factory():
            attempts.append(1)
            if len(attempts) == 1:
                raise RuntimeError("transient")
            # Second attempt succeeds.

        with patch.object(worker_main.asyncio, "sleep", side_effect=_sleep_stub):
            asyncio.run(_supervise("t", factory))

        self.assertEqual(len(attempts), 2)
        snap = task_status.snapshot()
        # Final state is running (clean exit resets to start, then exits).
        # The supervisor does not explicitly mark "running" on clean exit,
        # but it should NOT be "crashed".
        if "t" in snap:
            self.assertNotEqual(snap["t"]["state"], "crashed")

    def test_cancelled_error_propagates(self):
        async def factory():
            raise asyncio.CancelledError()

        with self.assertRaises(asyncio.CancelledError):
            asyncio.run(_supervise("t", factory))
        snap = task_status.snapshot()
        self.assertIn("t", snap)
        self.assertEqual(snap["t"]["state"], "stopped")

    def test_not_marked_crashed_during_retry(self):
        """During retry backoff the task must stay 'running', not 'crashed' —
        otherwise /health oscillates 200/503 and the Docker healthcheck may
        catch a 503 snapshot and mark the container unhealthy while it is
        actively recovering (#815)."""
        states_during_retry = []

        async def factory():
            raise RuntimeError("boom")

        async def fake_sleep(d):
            # Capture the state at the moment we enter the backoff sleep —
            # this is when /health would be polled by Docker.
            states_during_retry.append(task_status.snapshot().get("t", {}).get("state"))

        with patch.object(worker_main.asyncio, "sleep", side_effect=fake_sleep):
            asyncio.run(_supervise("t", factory))

        # MAX_RESTARTS sleep calls happened; none should have seen "crashed".
        self.assertEqual(len(states_during_retry), MAX_RESTARTS)
        for state in states_during_retry:
            self.assertNotEqual(state, "crashed")
        # After giving up, the final state IS crashed.
        snap = task_status.snapshot()
        self.assertEqual(snap["t"]["state"], "crashed")

    def test_backoff_grows_exponentially_and_caps(self):
        delays = []

        async def factory():
            raise RuntimeError("boom")

        async def fake_sleep(d):
            delays.append(d)

        with patch.object(worker_main.asyncio, "sleep", side_effect=fake_sleep):
            asyncio.run(_supervise("t", factory))

        # MAX_RESTARTS retries → MAX_RESTARTS sleep calls.
        self.assertEqual(len(delays), MAX_RESTARTS)
        expected = INITIAL_BACKOFF
        for i, d in enumerate(delays):
            self.assertEqual(d, expected)
            expected = min(expected * 2, MAX_BACKOFF)


if __name__ == "__main__":
    unittest.main()
