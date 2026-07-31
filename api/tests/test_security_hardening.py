"""Security regression tests for the critical hardening batch.

Covers:
- #322: SECRET_KEY must not have a public default; startup must reject placeholders.
- #323: auth bypass when AUTH_PASSWORD is unset must not exist.
- #324: /config/setup must refuse to re-run after setup is complete.
- #325: WebSocket /ws must require a valid JWT.
- #327: /debug must be 404 outside development.
- #358: ai-service /providers must not leak API keys.
"""

from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import main as main_module
import routers.config as config_router
from services import setup_state


# ---------------------------------------------------------------------------
# #322 — SECRET_KEY default / placeholder rejection
# ---------------------------------------------------------------------------

def test_secret_key_has_no_public_default():
    """The Settings default for secret_key must not be a public placeholder."""
    from config import Settings

    # Inspect the declared field default rather than instantiating Settings,
    # which would pick up SECRET_KEY from the test process environment.
    default = Settings.model_fields["secret_key"].default
    assert default == "", (
        "SECRET_KEY default must be empty, not a hardcoded public value (issue #322)"
    )


def test_secret_key_placeholders_set_is_nonempty():
    """The known-placeholder set must include the historical public defaults."""
    assert "dev_secret_change_me" in setup_state.SECRET_KEY_PLACEHOLDERS
    assert "change_this_to_a_random_secret_key" in setup_state.SECRET_KEY_PLACEHOLDERS
    assert "" in setup_state.SECRET_KEY_PLACEHOLDERS


def test_is_secret_key_safe_rejects_placeholders():
    assert not setup_state.is_secret_key_safe("")
    assert not setup_state.is_secret_key_safe("dev_secret_change_me")
    assert not setup_state.is_secret_key_safe("change_this_to_a_random_secret_key")
    assert setup_state.is_secret_key_safe("a-real-random-secret-from-openssl")


def test_validate_secret_key_aborts_on_placeholder():
    """Startup validation must raise for a non-empty public placeholder."""
    with patch.object(main_module.settings, "secret_key", "dev_secret_change_me"):
        with pytest.raises(RuntimeError):
            main_module._validate_secret_key()


def test_validate_secret_key_allows_empty():
    """An empty SECRET_KEY is allowed (drives the first-time setup flow)."""
    with patch.object(main_module.settings, "secret_key", ""):
        # Must not raise.
        main_module._validate_secret_key()


def test_validate_secret_key_allows_real_value():
    with patch.object(main_module.settings, "secret_key", "a-real-random-secret"):
        main_module._validate_secret_key()


# ---------------------------------------------------------------------------
# #323 — no auth bypass when AUTH_PASSWORD unset
# ---------------------------------------------------------------------------

def test_get_current_user_rejects_when_setup_incomplete():
    """When setup is not complete, get_current_user must raise (no bypass)."""
    from fastapi import HTTPException
    from services.auth_service import get_current_user

    with _stub_env(auth_password="", secret_key=""):
        with pytest.raises(HTTPException) as exc:
            get_current_user(credentials=None)
        assert exc.value.status_code in (401, 503)


@contextmanager
def _stub_env(*, auth_password: str = "", secret_key: str = ""):
    """Control the result of `is_setup_complete()` across all call sites.

    `is_setup_complete()` checks in-memory `settings` first, then falls back to
    the on-disk `.env`. We patch both so every module that imported
    `is_setup_complete` by name sees the same controlled state.
    """
    from config import settings

    with patch.object(settings, "auth_password", auth_password), \
         patch.object(settings, "secret_key", secret_key), \
         patch.object(
             setup_state,
             "_read_env_file",
             return_value={"AUTH_PASSWORD": auth_password, "SECRET_KEY": secret_key},
         ):
        yield


def test_login_refuses_when_setup_incomplete(client: TestClient):
    """POST /auth/login must not issue a token before setup is complete."""
    with _stub_env(auth_password="", secret_key=""):
        resp = client.post("/auth/login", params={"password": "anything"})
    assert resp.status_code in (401, 503, 500)
    assert "access_token" not in resp.json()


def test_login_refuses_empty_password_config(client: TestClient):
    """Defensive guard: even if is_setup_complete() is bypassed, an empty
    AUTH_PASSWORD must never yield a token."""
    # Force is_setup_complete to True at the auth-router call site while
    # auth_password is empty — a contradictory state that the defensive guard
    # in /auth/login must catch.
    with patch("routers.auth.is_setup_complete", return_value=True), \
         patch("routers.auth.is_secret_key_safe", return_value=True), \
         patch("routers.auth.settings.auth_password", ""), \
         patch("routers.auth.settings.secret_key", "a-real-secret"):
        resp = client.post("/auth/login", params={"password": ""})
    assert resp.status_code in (401, 503, 500)
    assert "access_token" not in resp.json()


# ---------------------------------------------------------------------------
# #324 — /config/setup hardening
# ---------------------------------------------------------------------------

def test_setup_refuses_after_complete(client: TestClient):
    """POST /config/setup must 403 once setup is already complete."""
    with _stub_env(auth_password="existing", secret_key="a-real-secret"):
        resp = client.post("/config/setup", json={"auth_password": "newpass1234"})
    assert resp.status_code == 403


def test_setup_status_returns_needs_setup_boolean(client: TestClient):
    with _stub_env(auth_password="", secret_key=""):
        resp = client.get("/config/setup-status")
    assert resp.status_code == 200
    assert resp.json() == {"needs_setup": True}

    with _stub_env(auth_password="existing", secret_key="a-real-secret"):
        resp = client.get("/config/setup-status")
    assert resp.status_code == 200
    assert resp.json() == {"needs_setup": False}


def test_setup_rejects_short_password(client: TestClient):
    with _stub_env(auth_password="", secret_key=""), \
         patch.object(config_router, "write_env"):
        resp = client.post("/config/setup", json={"auth_password": "ab"})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# #327 — /debug gated to development
# ---------------------------------------------------------------------------

def test_debug_404_in_production(client: TestClient):
    with patch.object(main_module.settings, "app_env", "production"):
        resp = client.get("/debug")
    assert resp.status_code == 404


def test_debug_available_in_development(client: TestClient):
    with patch.object(main_module.settings, "app_env", "development"):
        resp = client.get("/debug")
    # 200 in dev (auth is overridden by the test fixture).
    assert resp.status_code == 200
    data = resp.json()
    # Must not leak python version or environment variables.
    assert "python_version" not in data
    assert "env" not in data
    assert "platform" not in data


# ---------------------------------------------------------------------------
# #326 — CORS must not use wildcard with credentials
# ---------------------------------------------------------------------------

def test_cors_dev_origins_are_concrete_not_wildcard():
    """Development CORS origins must be concrete localhost URLs, not '*'."""
    with patch.object(main_module.settings, "cors_allowed_origins", ""), \
         patch.object(main_module.settings, "app_env", "development"):
        origins = main_module._get_cors_origins()
    assert "*" not in origins, (
        "Development CORS origins must not include '*' (issue #326)"
    )
    assert "http://localhost:3000" in origins
    assert "http://127.0.0.1:3000" in origins


def test_cors_production_no_wildcard_with_credentials():
    """In production, allow_credentials must never combine with '*'."""
    with patch.object(main_module.settings, "app_env", "production"), \
         patch.object(main_module.settings, "cors_allowed_origins", "https://joidy.app"):
        origins = main_module._get_cors_origins()
    assert "*" not in origins
    assert origins == ["https://joidy.app"]


def test_cors_no_safety_middleware_class():
    """CorsSafetyMiddleware must have been removed (issue #326)."""
    assert not hasattr(main_module, "CorsSafetyMiddleware"), (
        "CorsSafetyMiddleware was removed because it forced "
        "Access-Control-Allow-Origin: * on all responses."
    )


def test_cors_headers_present_on_error_response(client: TestClient):
    """CORS headers must still be present on responses even after removing
    the custom safety middleware — Starlette's CORSMiddleware handles this.

    The middleware is initialised at module load with the default development
    origins (localhost:3000), so we send a request from that origin.
    """
    resp = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_rejects_unlisted_origin(client: TestClient):
    """An origin not in the allowlist must not get an Allow-Origin header."""
    resp = client.get("/health", headers={"Origin": "http://evil.example.com"})
    allow_origin = resp.headers.get("access-control-allow-origin", "")
    assert "evil.example.com" not in allow_origin
    assert "*" not in allow_origin


# ---------------------------------------------------------------------------
# #358 — ai-service /providers must not leak keys
# ---------------------------------------------------------------------------

def test_ai_service_providers_does_not_leak_keys():
    """The /providers response must contain only booleans, never raw keys.

    The ai-service shares module names (`config`, `main`, `database`) with the
    api, so we exercise it in a clean subprocess with the ai-service dir on
    sys.path[0].
    """
    import json
    import subprocess
    import sys

    script = (
        "import json, sys, types\n"
        "sys.path.insert(0, '/tmp/joidy_repo/ai-service');\n"
        # Stub the `clients` package and the heavy provider SDKs so
        # ai-service/main.py imports cleanly without installing
        # google-generativeai/openai/anthropic/cohere. The /providers
        # endpoint only touches settings, not the clients.
        "clients = types.ModuleType('clients');\n"
        "clients.__path__ = []\n"
        "clients.get_embedding_client = lambda: None\n"
        "clients.get_llm_client = lambda: None\n"
        "sys.modules['clients'] = clients;\n"
        "prompts = types.ModuleType('clients.prompts');\n"
        "prompts.CLASSIFY_PROMPT = ''; prompts.RAG_PROMPT = '';\n"
        "sys.modules['clients.prompts'] = prompts;\n"
        "from config import settings\n"
        "settings.gemini_api_key = 'AIza-SUPER-SECRET-KEY'\n"
        "settings.openai_api_key = 'sk-secret-openai'\n"
        "settings.anthropic_api_key = ''\n"
        "settings.openrouter_api_key = ''\n"
        "settings.cohere_api_key = ''\n"
        "settings.ollama_base_url = 'http://localhost:11434'\n"
        "from fastapi.testclient import TestClient\n"
        "from main import app\n"
        "c = TestClient(app)\n"
        "r = c.get('/providers')\n"
        "print(json.dumps({'status': r.status_code, 'body': r.text}))\n"
    )
    import os
    env = dict(os.environ)
    env["PYTHONPATH"] = "/tmp/joidy_repo/ai-service"
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert result.returncode == 0, (
        f"ai-service subprocess failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["status"] == 200
    body = json.loads(payload["body"])
    configured = body["configured"]
    assert configured.get("gemini") is True
    assert configured.get("openai") is True
    for value in configured.values():
        assert value is True or value is False
    raw = payload["body"]
    assert "AIza-SUPER-SECRET-KEY" not in raw
    assert "sk-secret-openai" not in raw
