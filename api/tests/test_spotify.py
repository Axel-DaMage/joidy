"""Tests for Spotify integration router and service."""

from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

from services import oauth_state

SPOTIFY_TOKEN_HEADER = {"X-Spotify-Token": "xyz"}


def _configure_spotify(monkeypatch):
    monkeypatch.setattr("services.spotify_service.settings.spotify_client_id", "spotify-client-id")
    monkeypatch.setattr("services.spotify_service.settings.spotify_client_secret", "spotify-client-secret")
    monkeypatch.setattr(
        "services.spotify_service.settings.spotify_redirect_uri",
        "http://localhost:8000/integrations/spotify/callback",
    )
    monkeypatch.setattr("config.settings.secret_key", "test-secret")


def _auth_url_state(client) -> str:
    """Round-trip helper: fetch /auth and extract the signed state param."""
    url: str = client.get("/integrations/spotify/auth").json()["url"]
    return parse_qs(urlparse(url).query)["state"][0]


def test_spotify_auth_url_unconfigured(client):
    resp = client.get("/integrations/spotify/auth")
    assert resp.status_code == 400


def test_spotify_auth_url_configured(client, monkeypatch):
    _configure_spotify(monkeypatch)

    resp = client.get("/integrations/spotify/auth")
    assert resp.status_code == 200
    data = resp.json()
    assert "accounts.spotify.com" in data["url"]
    assert "spotify-client-id" in data["url"]
    # CSRF nonce must be embedded so Spotify echoes it back to /callback (#1328).
    state = parse_qs(urlparse(data["url"]).query)["state"][0]
    assert oauth_state.verify_state(state, "spotify") is True


def test_spotify_callback_missing_code(client):
    resp = client.get("/integrations/spotify/callback")
    assert resp.status_code == 400


def test_spotify_callback_error(client):
    resp = client.get("/integrations/spotify/callback?error=access_denied")
    assert resp.status_code == 400


def test_spotify_callback_rejects_missing_state(client, monkeypatch):
    _configure_spotify(monkeypatch)

    exchange = AsyncMock()
    with patch("services.spotify_service.exchange_code", new=exchange):
        resp = client.get("/integrations/spotify/callback?code=abc123")

    assert resp.status_code == 400
    exchange.assert_not_awaited()  # denied before any token exchange


def test_spotify_callback_rejects_wrong_state(client, monkeypatch):
    _configure_spotify(monkeypatch)

    exchange = AsyncMock()
    with patch("services.spotify_service.exchange_code", new=exchange):
        resp = client.get("/integrations/spotify/callback?code=abc123&state=forged")

    assert resp.status_code == 400
    exchange.assert_not_awaited()


def test_spotify_callback_rejects_state_from_other_provider(client, monkeypatch):
    # A state legitimately signed for Strava must not pass at Spotify's callback.
    _configure_spotify(monkeypatch)
    state = oauth_state.generate_state("strava")

    exchange = AsyncMock()
    with patch("services.spotify_service.exchange_code", new=exchange):
        resp = client.get(f"/integrations/spotify/callback?code=abc123&state={state}")

    assert resp.status_code == 400
    exchange.assert_not_awaited()


def test_spotify_callback_exchanges_code(client, monkeypatch):
    _configure_spotify(monkeypatch)

    fake_response = MagicMock()
    fake_response.json.return_value = {
        "access_token": "ACCESS",
        "refresh_token": "REFRESH",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "user-read-recently-played",
    }
    fake_response.raise_for_status.return_value = None

    # Full round-trip: state issued by /auth must be echoed back by Spotify.
    state = _auth_url_state(client)
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        resp = client.get(f"/integrations/spotify/callback?code=abc123&state={state}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] == "ACCESS"
    assert data["refresh_token"] == "REFRESH"


def test_spotify_recently_played(client, monkeypatch):
    _configure_spotify(monkeypatch)

    fake_response = MagicMock()
    fake_response.json.return_value = {"items": [{"track": {"name": "Song 1"}}]}
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/spotify/recently-played", headers=SPOTIFY_TOKEN_HEADER)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["track"]["name"] == "Song 1"


def test_spotify_data_endpoints_reject_query_token(client):
    # ?token= must not be accepted — Bearer credentials never travel in URLs
    # (access logs, browser history, Referer). Missing header → 422 (#1328).
    for path in ("recently-played", "top-tracks", "playlists"):
        resp = client.get(f"/integrations/spotify/{path}?token=xyz")
        assert resp.status_code == 422, path
