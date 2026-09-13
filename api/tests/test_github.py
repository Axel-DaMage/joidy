"""Tests for GitHub integration router (username mode, device flow, error handling)."""

from unittest.mock import AsyncMock, MagicMock, patch


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
