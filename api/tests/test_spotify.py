"""Tests for Spotify integration router and service."""

from unittest.mock import AsyncMock, MagicMock, patch


def test_spotify_auth_url_unconfigured(client):
    resp = client.get("/integrations/spotify/auth")
    assert resp.status_code == 400


def test_spotify_auth_url_configured(client, monkeypatch):
    monkeypatch.setattr(
        "services.spotify_service.settings.spotify_client_id", "spotify-client-id"
    )
    monkeypatch.setattr(
        "services.spotify_service.settings.spotify_redirect_uri",
        "http://localhost:8000/integrations/spotify/callback",
    )

    resp = client.get("/integrations/spotify/auth")
    assert resp.status_code == 200
    data = resp.json()
    assert "accounts.spotify.com" in data["url"]
    assert "spotify-client-id" in data["url"]


def test_spotify_callback_missing_code(client):
    resp = client.get("/integrations/spotify/callback")
    assert resp.status_code == 400


def test_spotify_callback_error(client):
    resp = client.get("/integrations/spotify/callback?error=access_denied")
    assert resp.status_code == 400


def test_spotify_callback_exchanges_code(client, monkeypatch):
    monkeypatch.setattr(
        "services.spotify_service.settings.spotify_client_id", "spotify-client-id"
    )
    monkeypatch.setattr(
        "services.spotify_service.settings.spotify_client_secret",
        "spotify-client-secret",
    )
    monkeypatch.setattr(
        "services.spotify_service.settings.spotify_redirect_uri",
        "http://localhost:8000/integrations/spotify/callback",
    )

    fake_response = MagicMock()
    fake_response.json.return_value = {
        "access_token": "ACCESS",
        "refresh_token": "REFRESH",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "user-read-recently-played",
    }
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/spotify/callback?code=abc123")

    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] == "ACCESS"
    assert data["refresh_token"] == "REFRESH"


def test_spotify_recently_played(client, monkeypatch):
    monkeypatch.setattr(
        "services.spotify_service.settings.spotify_client_id", "spotify-client-id"
    )
    monkeypatch.setattr(
        "services.spotify_service.settings.spotify_redirect_uri",
        "http://localhost:8000/integrations/spotify/callback",
    )

    fake_response = MagicMock()
    fake_response.json.return_value = {
        "items": [{"track": {"name": "Song 1"}}]
    }
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/spotify/recently-played?token=xyz")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["track"]["name"] == "Song 1"
