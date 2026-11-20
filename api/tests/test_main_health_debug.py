"""Coverage for ``main.py`` health/debug/lifespan/middleware paths (#1401).

The app object is built at import time, so router-level tests never reach the
lifespan guards, the ``/debug`` diagnostic endpoint, the CORS safety middleware
error path, or the static-file auth bypass. These tests exercise them directly.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import main as main_module
import pytest
from config import settings
from fastapi.testclient import TestClient
from models.gamification import UserStats
from services.timezone_utils import get_local_today
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


def _run_lifespan():
    """Enter+exit the app lifespan once inside a fresh event loop."""

    async def _go():
        async with main_module.lifespan(main_module.app):
            pass

    asyncio.run(_go())


class _EmptyGoalsDB:
    """Stand-in for ``SessionLocal`` whose goals table reports empty.

    The lifespan vault-restore block only runs its restore call when
    ``Goal.count() == 0``; this fake makes that deterministic regardless of
    residue left by other tests in the same xdist worker.
    """

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def query(self, _model):
        outer = self

        class _Query:
            def count(self):
                return 0

            def __getattr__(self, name):
                return getattr(outer, name)

        return _Query()


# ─── Lifespan startup guards ──────────────────────────────────────────────────


def test_lifespan_refuses_production_without_auth_password(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "auth_password", "")
    with pytest.raises(RuntimeError, match="AUTH_PASSWORD"):
        _run_lifespan()


def test_lifespan_refuses_production_with_placeholder_secret_key(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "auth_password", "real-prod-password")
    monkeypatch.setattr(settings, "secret_key", "change_this_to_a_random_secret_key")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        _run_lifespan()


def test_lifespan_dev_mode_runs_and_restores_vault_goals(monkeypatch):
    """Non-test, non-production env runs the vault auto-restore block (#504)."""
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "auth_password", "")
    monkeypatch.setattr("database.SessionLocal", lambda: _EmptyGoalsDB())

    fake_restore = MagicMock(return_value={"status": "ok", "restored": 3, "skipped": 0})
    with patch("services.joidy_vault_writer.restore_goals_from_vault", fake_restore):
        _run_lifespan()
    fake_restore.assert_called_once()


def test_lifespan_dev_mode_survives_restore_failure(monkeypatch):
    """A vault-restore exception is logged, never fatal (#504)."""
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "auth_password", "")
    monkeypatch.setattr("database.SessionLocal", lambda: _EmptyGoalsDB())

    fake_restore = MagicMock(side_effect=RuntimeError("vault exploded"))
    with patch("services.joidy_vault_writer.restore_goals_from_vault", fake_restore):
        _run_lifespan()  # must not raise
    fake_restore.assert_called_once()


# ─── Health endpoints ─────────────────────────────────────────────────────────


def test_health_ready_ok(client: TestClient):
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["checks"]["database"] == "ok"
    assert data["checks"]["cache"] == "ok"
    # ai-service is unreachable inside the test network → degraded, not 500.
    assert data["status"] in ("ready", "degraded")


def test_health_ready_ai_disabled(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "ai_service_enabled", False)
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json()["checks"]["ai_service"] == "disabled"


def _mock_ai_health(status_code: int, body: dict):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = body
    mock_instance = MagicMock()
    mock_instance.get = AsyncMock(return_value=mock_resp)
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=None)
    return mock_instance


def test_health_ready_ai_healthy(client: TestClient):
    with patch("main.http_client", return_value=_mock_ai_health(200, {"status": "ok"})):
        resp = client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json()["checks"]["ai_service"] == "ok"


def test_health_ready_ai_unhealthy_status(client: TestClient):
    with patch("main.http_client", return_value=_mock_ai_health(503, {})):
        resp = client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json()["checks"]["ai_service"] == "ai_unhealthy"


def test_health_ready_cache_check_failure(client: TestClient):
    # health_ready does a local ``from services.response_cache import ...`` so
    # the patch must target the source module, not the main.py binding.
    with patch("services.response_cache.get_cache_stats", side_effect=RuntimeError("cache gone")):
        resp = client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json()["checks"]["cache"] == "cache_unreachable"
    assert resp.json()["status"] == "degraded"


def test_health_cache_endpoint(client: TestClient):
    resp = client.get("/health/cache")
    assert resp.status_code == 200
    assert resp.json()["initialized"] is True


def test_root_endpoint(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Joidy API"


# ─── /debug endpoint ──────────────────────────────────────────────────────────


def test_debug_endpoint_returns_diagnostics(client: TestClient):
    resp = client.get("/debug")
    assert resp.status_code == 200
    data = resp.json()
    assert "timestamp" in data
    assert "python_version" in data
    assert "database" in data
    assert "recent_failures" in data


@pytest.mark.real_commit
def test_debug_endpoint_includes_gamification_stats(client: TestClient, db_session):
    """With a committed UserStats row the /debug gamification section fills in."""
    stats = db_session.get(UserStats, 1)
    if stats is None:
        stats = UserStats(id=1)
        db_session.add(stats)
    stats.total_xp = 1234
    stats.current_streak = 7
    stats.plant_stage = 2
    stats.last_activity_date = get_local_today()
    db_session.commit()

    resp = client.get("/debug")
    assert resp.status_code == 200
    gami = resp.json()["gamification"]
    assert gami["total_xp"] == 1234
    assert gami["current_streak"] == 7
    assert gami["plant_stage"] == 2
    assert gami["last_activity"] is not None


# ─── CorsSafetyMiddleware ─────────────────────────────────────────────────────


def _scope(headers: list[tuple[bytes, bytes]] | None = None) -> dict:
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/notes/",
        "raw_path": b"/notes/",
        "query_string": b"",
        "root_path": "",
        "headers": headers or [],
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }


def test_cors_safety_middleware_returns_500_on_exception():
    """An unhandled endpoint exception still yields a CORS-safe 500 JSON."""

    async def exploding_call_next(request):
        raise RuntimeError("boom")

    async def _go():
        mw = main_module.CorsSafetyMiddleware(app=main_module.app)
        return await mw.dispatch(Request(_scope()), exploding_call_next)

    resp = asyncio.run(_go())
    assert resp.status_code == 500
    assert resp.body == b'{"detail":"Internal server error"}'


def test_cors_safety_middleware_echoes_allowed_origin(monkeypatch):
    """With a specific allowlist the request Origin is echoed back."""
    monkeypatch.setattr(main_module, "_cors_origins", ["https://joidy.example.com"])

    async def ok_call_next(request):
        return Response("ok", status_code=200)

    async def _go():
        mw = main_module.CorsSafetyMiddleware(app=main_module.app)
        req = Request(_scope(headers=[(b"origin", b"https://joidy.example.com")]))
        allowed = await mw.dispatch(req, ok_call_next)
        req2 = Request(_scope(headers=[(b"origin", b"https://evil.example.com")]))
        denied = await mw.dispatch(req2, ok_call_next)
        return allowed, denied

    allowed, denied = asyncio.run(_go())
    assert allowed.status_code == 200
    assert allowed.headers["Access-Control-Allow-Origin"] == "https://joidy.example.com"
    assert "GET" in allowed.headers["Access-Control-Allow-Methods"]
    assert "Access-Control-Allow-Origin" not in denied.headers


# ─── _get_cors_origins ────────────────────────────────────────────────────────


def test_get_cors_origins_from_settings(monkeypatch):
    monkeypatch.setattr(settings, "cors_allowed_origins", "https://a.example.com, https://b.example.com ,")
    assert main_module._get_cors_origins() == ["https://a.example.com", "https://b.example.com"]


def test_get_cors_origins_production_empty(monkeypatch):
    monkeypatch.setattr(settings, "cors_allowed_origins", "")
    monkeypatch.setattr(settings, "app_env", "production")
    assert main_module._get_cors_origins() == []


def test_get_cors_origins_dev_fallback(monkeypatch):
    monkeypatch.setattr(settings, "cors_allowed_origins", "")
    monkeypatch.setattr(settings, "app_env", "development")
    assert main_module._get_cors_origins() == ["*"]


# ─── SafeStaticFiles._unauthorized ────────────────────────────────────────────


def test_static_files_unauthorized_production_without_auth(monkeypatch):
    """Production + no AUTH_PASSWORD fails closed on /uploads (#1279)."""
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "auth_password", "")

    resp = main_module.SafeStaticFiles._unauthorized(_scope())
    assert isinstance(resp, JSONResponse)
    assert resp.status_code == 401


def test_static_files_unauthorized_dev_bypass(monkeypatch):
    """Outside production with no AUTH_PASSWORD the bypass allows the request."""
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "auth_password", "")
    assert main_module.SafeStaticFiles._unauthorized(_scope()) is None
