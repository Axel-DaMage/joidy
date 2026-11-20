"""Tests for #1291 — /health and /health/ready must return fixed reason
strings instead of raw exception text (information disclosure)."""

from unittest.mock import MagicMock, patch

import database
import pytest
from fastapi.testclient import TestClient

_BOOM = "boom-internal-detail-9f8e7d"  # sentinel that must never leak


def _failing_engine(exc):
    fake = MagicMock()
    fake.connect.side_effect = exc
    return fake


@pytest.mark.parametrize("path", ["/health", "/health/ready"])
def test_db_failure_returns_fixed_reason(client: TestClient, path):
    """A DB outage surfaces as 'db_unreachable' — never raw exception text."""
    with patch.object(database, "engine", _failing_engine(RuntimeError(_BOOM))):
        resp = client.get(path)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["checks"]["database"] == "db_unreachable"
    assert _BOOM not in resp.text
    assert "RuntimeError" not in resp.text


def test_health_ready_never_leaks_exception_text(client: TestClient):
    """Every failing check reports a fixed string — no exception fragments."""
    with patch.object(database, "engine", _failing_engine(ConnectionError(_BOOM))):
        resp = client.get("/health/ready")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    # ai-service is unreachable in the test environment — bounded values only.
    assert body["checks"]["database"] == "db_unreachable"
    assert body["checks"]["ai_service"] in ("ai_unreachable", "ai_unhealthy", "disabled")
    for value in body["checks"].values():
        assert not str(value).startswith(("error:", "unavailable:")), value
    assert _BOOM not in resp.text
    assert "ConnectionError" not in resp.text
