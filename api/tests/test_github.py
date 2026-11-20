"""Tests for GitHub integration router (username mode, device flow, error handling)."""

from unittest.mock import AsyncMock, MagicMock, patch

from services import oauth_state


def test_github_status_unconfigured(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "")
    monkeypatch.setattr("routers.integrations.github.settings.github_username", "")

    resp = client.get("/integrations/github/status")
    assert resp.status_code == 200
    assert resp.json() == {"connected": False, "username": None}


def test_github_status_token(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "fake-token")

    fake_response = MagicMock()
    fake_response.json.return_value = {"login": "octocat"}
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/github/status")
        assert resp.status_code == 200
        assert resp.json() == {"connected": True, "username": "octocat"}


def test_github_status_username_only(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "")
    monkeypatch.setattr("routers.integrations.github.settings.github_username", "octocat")

    fake_response = MagicMock()
    fake_response.json.return_value = {"login": "octocat"}
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/github/status")
        assert resp.status_code == 200
        assert resp.json() == {"connected": True, "username": "octocat"}


def test_github_repos_username_only(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_token", "")
    monkeypatch.setattr("routers.integrations.github.settings.github_username", "octocat")

    fake_response = MagicMock()
    fake_response.json.return_value = [
        {
            "id": 1,
            "name": "Hello-World",
            "full_name": "octocat/Hello-World",
            "description": "My first repo",
            "private": False,
            "html_url": "https://github.com/octocat/Hello-World",
            "default_branch": "master",
            "updated_at": "2026-01-01T00:00:00Z",
        }
    ]
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/github/repos")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["repos"]) == 1
        assert data["repos"][0]["full_name"] == "octocat/Hello-World"
        assert "color" in data["repos"][0]


def test_github_device_flow_unconfigured(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_client_id", "")

    resp = client.get("/integrations/github/oauth/device/start")
    assert resp.status_code == 400
    assert "GitHub OAuth not configured" in resp.json()["detail"]


def test_github_device_flow_start_success(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_client_id", "my-client-id")

    fake_response = MagicMock()
    fake_response.json.return_value = {
        "device_code": "dev123",
        "user_code": "ABCD-1234",
        "verification_uri": "https://github.com/login/device",
        "expires_in": 900,
        "interval": 5,
    }
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/github/oauth/device/start")
        assert resp.status_code == 200
        data = resp.json()
        assert data["device_code"] == "dev123"
        assert data["user_code"] == "ABCD-1234"


def test_github_device_flow_polling_pending(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_client_id", "my-client-id")

    fake_response = MagicMock()
    fake_response.json.return_value = {"error": "authorization_pending"}
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        resp = client.post("/integrations/github/oauth/device/polling?device_code=dev123")
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"


def test_github_device_flow_polling_authorized(client, monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_client_id", "my-client-id")
    monkeypatch.setattr("routers.integrations.github.settings.github_client_secret", "my-secret")

    fake_response = MagicMock()
    fake_response.json.return_value = {
        "access_token": "gho_token123",
        "token_type": "bearer",
        "scope": "repo,read:user",
    }
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        resp = client.post("/integrations/github/oauth/device/polling?device_code=dev123")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "authorized"
        assert data["access_token"] == "gho_token123"


def _configure_github_web_flow(monkeypatch):
    monkeypatch.setattr("routers.integrations.github.settings.github_client_id", "my-client-id")
    monkeypatch.setattr("routers.integrations.github.settings.github_client_secret", "my-secret")
    monkeypatch.setattr(
        "routers.integrations.github.settings.github_oauth_web_url",
        "http://localhost:8000/integrations/github/oauth/callback",
    )
    monkeypatch.setattr("config.settings.secret_key", "test-secret")


def test_github_web_flow_start_includes_state(client, monkeypatch):
    _configure_github_web_flow(monkeypatch)

    resp = client.get("/integrations/github/oauth/web/start")
    assert resp.status_code == 200
    data = resp.json()
    # CSRF nonce must be embedded so GitHub echoes it back to /callback (#1280).
    assert f"state={data['state']}" in data["authorize_url"]
    assert oauth_state.verify_state(data["state"], "github") is True


def test_github_oauth_callback_rejects_missing_state(client, monkeypatch):
    _configure_github_web_flow(monkeypatch)

    post = AsyncMock()
    with patch("httpx.AsyncClient.post", new=post):
        resp = client.get("/integrations/github/oauth/callback?code=abc123")

    assert resp.status_code == 403
    post.assert_not_called()  # denied before any token exchange


def test_github_oauth_callback_rejects_wrong_state(client, monkeypatch):
    _configure_github_web_flow(monkeypatch)

    post = AsyncMock()
    with patch("httpx.AsyncClient.post", new=post):
        resp = client.get("/integrations/github/oauth/callback?code=abc123&state=forged")

    assert resp.status_code == 403
    post.assert_not_called()


def test_github_oauth_callback_rejects_state_from_other_provider(client, monkeypatch):
    # A state legitimately signed for Google must not pass at GitHub's callback.
    _configure_github_web_flow(monkeypatch)
    state = oauth_state.generate_state("google")

    post = AsyncMock()
    with patch("httpx.AsyncClient.post", new=post):
        resp = client.get(f"/integrations/github/oauth/callback?code=abc123&state={state}")

    assert resp.status_code == 403
    post.assert_not_called()


def test_github_oauth_callback_valid_state(client, monkeypatch):
    _configure_github_web_flow(monkeypatch)
    state = oauth_state.generate_state("github")

    fake_response = MagicMock()
    fake_response.json.return_value = {
        "access_token": "gho_token123",
        "token_type": "bearer",
        "scope": "repo,read:user",
    }
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        resp = client.get(f"/integrations/github/oauth/callback?code=abc123&state={state}")

    assert resp.status_code == 200
    assert resp.json()["status"] == "authorized"
