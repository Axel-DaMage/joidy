"""Tests for Google integration router and service."""

from unittest.mock import AsyncMock, MagicMock, patch


def test_google_auth_url_unconfigured(client):
    resp = client.get("/integrations/google/auth")
    assert resp.status_code == 400


def test_google_auth_url_configured(client, monkeypatch):
    monkeypatch.setattr(
        "services.google_service.settings.google_client_id", "google-client-id"
    )
    monkeypatch.setattr(
        "services.google_service.settings.google_redirect_uri",
        "http://localhost:8000/integrations/google/callback",
    )

    resp = client.get("/integrations/google/auth")
    assert resp.status_code == 200
    data = resp.json()
    assert "accounts.google.com" in data["url"]
    assert "google-client-id" in data["url"]


def test_google_callback_missing_code(client):
    resp = client.get("/integrations/google/callback")
    assert resp.status_code == 400


def test_google_callback_error(client):
    resp = client.get("/integrations/google/callback?error=access_denied")
    assert resp.status_code == 400


def test_google_callback_exchanges_code(client, monkeypatch):
    monkeypatch.setattr(
        "services.google_service.settings.google_client_id", "google-client-id"
    )
    monkeypatch.setattr(
        "services.google_service.settings.google_client_secret", "google-client-secret"
    )
    monkeypatch.setattr(
        "services.google_service.settings.google_redirect_uri",
        "http://localhost:8000/integrations/google/callback",
    )

    fake_response = MagicMock()
    fake_response.json.return_value = {
        "access_token": "ACCESS",
        "refresh_token": "REFRESH",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "calendar tasks",
    }
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/google/callback?code=abc123")

    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] == "ACCESS"
    assert data["refresh_token"] == "REFRESH"


def test_google_calendars_list(client, monkeypatch):
    monkeypatch.setattr(
        "services.google_service.settings.google_client_id", "google-client-id"
    )
    monkeypatch.setattr(
        "services.google_service.settings.google_redirect_uri",
        "http://localhost:8000/integrations/google/callback",
    )

    fake_response = MagicMock()
    fake_response.json.return_value = {"items": [{"id": "primary", "summary": "Primary"}]}
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/google/calendars?token=xyz")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "primary"


def test_google_gmail_messages_list(client, monkeypatch):
    monkeypatch.setattr(
        "services.google_service.settings.google_client_id", "google-client-id"
    )
    monkeypatch.setattr(
        "services.google_service.settings.google_redirect_uri",
        "http://localhost:8000/integrations/google/callback",
    )

    fake_response = MagicMock()
    fake_response.json.return_value = {
        "messages": [{"id": "msg1", "threadId": "t1"}]
    }
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/google/gmail?token=xyz&max_results=5")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "msg1"


def test_google_contacts_list(client, monkeypatch):
    monkeypatch.setattr(
        "services.google_service.settings.google_client_id", "google-client-id"
    )
    monkeypatch.setattr(
        "services.google_service.settings.google_redirect_uri",
        "http://localhost:8000/integrations/google/callback",
    )

    fake_response = MagicMock()
    fake_response.json.return_value = {
        "connections": [{"resourceName": "people/1", "names": [{"displayName": "Ada"}]}]
    }
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/google/contacts?token=xyz&page_size=10")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["resourceName"] == "people/1"
