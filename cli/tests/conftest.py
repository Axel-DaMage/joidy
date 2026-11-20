"""Shared fixtures: a CliRunner plus an httpx.MockTransport API double."""

from __future__ import annotations

import json
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from joidy_cli import client as client_mod
from joidy_cli import config as config_mod
from joidy_cli.main import app
from typer.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Every test gets a throwaway config dir and a clean env."""
    monkeypatch.setenv("JOIDY_CONFIG_DIR", str(tmp_path / "cfg"))
    for var in ("JOIDY_TOKEN", "JOIDY_API_URL", "JOIDY_DIR", "JOIDY_STACK_CLI"):
        monkeypatch.delenv(var, raising=False)
    yield


@pytest.fixture
def invoke(runner):
    def _invoke(*args: str, stdin: str | None = None):
        return runner.invoke(app, list(args), input=stdin)

    return _invoke


@pytest.fixture
def api(monkeypatch):
    """Route ApiClient traffic through httpx.MockTransport.

    ``api.respond`` is a mutable holder: assign a new handler
    ``api.respond["fn"] = lambda request: httpx.Response(...)`` to steer
    responses per test. ``api.records`` collects every request.
    """
    records: list[httpx.Request] = []
    respond: dict[str, Callable[[httpx.Request], httpx.Response]] = {
        "fn": lambda request: httpx.Response(200, json={"ok": True})
    }

    def handler(request: httpx.Request) -> httpx.Response:
        records.append(request)
        return respond["fn"](request)

    transport = httpx.MockTransport(handler)

    def fake_create(api_url=None, token=None):
        # Real flag/env/config resolution; only the transport is mocked.
        url = config_mod.get_api_url(api_url)
        resolved_token, _ = config_mod.get_token(token)
        return client_mod.ApiClient(url, resolved_token or "test-token", transport=transport)

    monkeypatch.setattr(client_mod, "create", fake_create)
    return SimpleNamespace(records=records, respond=respond)


def last_body(api) -> dict[str, Any]:
    return json.loads(api.records[-1].content.decode())


def output_json(result) -> Any:
    return json.loads(result.stdout or result.output)


def combined(result) -> str:
    return (result.output or "") + (getattr(result, "stderr", "") or "")
