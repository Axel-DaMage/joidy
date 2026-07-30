"""Tests for Strava integration router and service."""

from unittest.mock import AsyncMock, MagicMock, patch


def test_strava_auth_url_unconfigured(client):
    resp = client.get("/integrations/strava/auth")
    assert resp.status_code == 400


def test_strava_auth_url_configured(client, monkeypatch):
    monkeypatch.setattr(
        "services.strava_service.settings.strava_client_id", "strava-client-id"
    )
    monkeypatch.setattr(
        "services.strava_service.settings.strava_redirect_uri",
        "http://localhost:8000/integrations/strava/callback",
    )

    resp = client.get("/integrations/strava/auth")
    assert resp.status_code == 200
    data = resp.json()
    assert "strava.com" in data["url"]
    assert "strava-client-id" in data["url"]


def test_strava_callback_missing_code(client):
    resp = client.get("/integrations/strava/callback")
    assert resp.status_code == 400


def test_strava_callback_error(client):
    resp = client.get("/integrations/strava/callback?error=access_denied")
    assert resp.status_code == 400


def test_strava_callback_exchanges_code(client, monkeypatch):
    monkeypatch.setattr(
        "services.strava_service.settings.strava_client_id", "strava-client-id"
    )
    monkeypatch.setattr(
        "services.strava_service.settings.strava_client_secret", "strava-client-secret"
    )
    monkeypatch.setattr(
        "services.strava_service.settings.strava_redirect_uri",
        "http://localhost:8000/integrations/strava/callback",
    )

    fake_response = MagicMock()
    fake_response.json.return_value = {
        "access_token": "ACCESS",
        "refresh_token": "REFRESH",
        "expires_in": 3600,
        "token_type": "Bearer",
        "athlete": {"id": 1, "firstname": "Ada"},
    }
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/strava/callback?code=abc123")

    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] == "ACCESS"
    assert data["athlete"]["firstname"] == "Ada"


def test_strava_activities_list(client, monkeypatch):
    monkeypatch.setattr(
        "services.strava_service.settings.strava_client_id", "strava-client-id"
    )
    monkeypatch.setattr(
        "services.strava_service.settings.strava_redirect_uri",
        "http://localhost:8000/integrations/strava/callback",
    )

    fake_response = MagicMock()
    fake_response.json.return_value = [{"id": 123, "name": "Morning Run"}]
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/strava/activities?token=xyz")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Morning Run"
