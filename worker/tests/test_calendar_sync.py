"""Tests for the Google Calendar sync trigger task (#1134).

The worker only pulls the API's POST /integrations/google/calendar/sync;
HTTP is mocked. Covers the happy path, token-expiry retry, "not connected"
skip, and network errors not raising (the supervisor loop handles logging).
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tasks import calendar_sync


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _client_mock(resp):
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.post = AsyncMock(return_value=resp)
    return client


def _json_resp(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    return resp


class TriggerCalendarSyncTest(unittest.TestCase):
    def test_success(self):
        resp = _json_resp(json_data={"synced_at": "...", "calendars": [{"calendar_id": "primary"}]})
        client = _client_mock(resp)
        with (
            patch.object(calendar_sync.httpx, "AsyncClient", return_value=client),
            patch.object(calendar_sync.joidy_daily_writer, "_get_auth_token", new=AsyncMock(return_value="tok")),
        ):
            self.assertTrue(_run(calendar_sync.trigger_calendar_sync()))
        client.post.assert_awaited_once()
        headers = client.post.call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], "Bearer tok")

    def test_401_retries_once_with_fresh_token(self):
        first = _json_resp(status_code=401)
        second = _json_resp(json_data={"calendars": []})
        client = _client_mock(first)
        client.post = AsyncMock(side_effect=[first, second])
        # _get_auth_token returns a new token the second time it is called.
        tokens = iter(["stale", "fresh"])
        with (
            patch.object(calendar_sync.httpx, "AsyncClient", return_value=client),
            patch.object(
                calendar_sync.joidy_daily_writer,
                "_get_auth_token",
                new=AsyncMock(side_effect=lambda _: next(tokens)),
            ),
        ):
            self.assertTrue(_run(calendar_sync.trigger_calendar_sync()))
        self.assertEqual(client.post.await_count, 2)
        headers = client.post.call_args.kwargs["headers"]
        self.assertEqual(headers["Authorization"], "Bearer fresh")

    def test_google_not_connected_returns_false(self):
        client = _client_mock(_json_resp(status_code=401))
        with (
            patch.object(calendar_sync.httpx, "AsyncClient", return_value=client),
            patch.object(calendar_sync.joidy_daily_writer, "_get_auth_token", new=AsyncMock(return_value="tok")),
        ):
            self.assertFalse(_run(calendar_sync.trigger_calendar_sync()))

    def test_network_error_propagates(self):
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
        with (
            patch.object(calendar_sync.httpx, "AsyncClient", return_value=client),
            patch.object(calendar_sync.joidy_daily_writer, "_get_auth_token", new=AsyncMock(return_value="tok")),
        ):
            with self.assertRaises(httpx.ConnectError):
                _run(calendar_sync.trigger_calendar_sync())


if __name__ == "__main__":
    unittest.main()
