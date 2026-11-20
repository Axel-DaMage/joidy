"""joidy auth login/logout/status."""

import stat
import tomllib

import httpx
from joidy_cli import config

from tests.conftest import combined, last_body, output_json


def test_login_stores_token(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(200, json={"access_token": "jwt-abc", "token_type": "bearer"})
    result = invoke("auth", "login", "--password", "s3cret")
    assert result.exit_code == 0, combined(result)

    request = api.records[-1]
    assert request.method == "POST"
    assert request.url.path == "/auth/login"
    assert last_body(api) == {"username": "user", "password": "s3cret"}

    path = config.config_path()
    stored = tomllib.loads(path.read_text())
    assert stored["auth"]["token"] == "jwt-abc"
    assert stored["api"]["url"] == "http://localhost:8000"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600

    data = output_json(result)
    assert data["status"] == "ok"
    assert "jwt-abc" not in result.output  # never echo the token


def test_login_password_from_stdin(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(200, json={"access_token": "tok"})
    result = invoke("auth", "login", "--password", "-", stdin="pw-from-stdin\n")
    assert result.exit_code == 0
    assert last_body(api)["password"] == "pw-from-stdin"


def test_login_requires_password_non_tty(invoke, api):
    result = invoke("auth", "login")
    assert result.exit_code == 2
    assert "--password" in combined(result)


def test_login_401_exit_code(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(401, json={"detail": "Invalid credentials"})
    result = invoke("auth", "login", "--password", "wrong")
    assert result.exit_code == 3


def test_auth_status_unauthenticated(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(200, json={"enabled": True})
    result = invoke("auth", "status")
    assert result.exit_code == 0
    data = output_json(result)
    assert data["reachable"] is True
    assert data["auth_enabled"] is True
    assert data["token_source"] in {"none", "config"}
    assert data["api_url"] == "http://localhost:8000"


def test_auth_status_env_token(invoke, api, monkeypatch):
    monkeypatch.setenv("JOIDY_TOKEN", "env-token")
    api.respond["fn"] = lambda req: httpx.Response(200, json={"enabled": True})
    result = invoke("auth", "status")
    data = output_json(result)
    assert data["authenticated"] is True
    assert data["token_source"] == "env"


def test_logout_clears_token(invoke, api):
    config.store_token("tok")
    assert config.get_token()[0] == "tok"
    result = invoke("auth", "logout")
    assert result.exit_code == 0
    assert config.get_token()[0] is None


def test_api_url_env_override(invoke, api, monkeypatch):
    monkeypatch.setenv("JOIDY_API_URL", "http://remote:9000")
    api.respond["fn"] = lambda req: httpx.Response(200, json={"enabled": True})
    result = invoke("auth", "status")
    assert output_json(result)["api_url"] == "http://remote:9000"
