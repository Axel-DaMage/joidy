"""Tests for Strava integration router and service."""

from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

from services import oauth_state

STRAVA_TOKEN_HEADER = {"X-Strava-Token": "xyz"}


def _configure_strava(monkeypatch):
    monkeypatch.setattr("services.strava_service.settings.strava_client_id", "strava-client-id")
    monkeypatch.setattr("services.strava_service.settings.strava_client_secret", "strava-client-secret")
    monkeypatch.setattr(
        "services.strava_service.settings.strava_redirect_uri",
        "http://localhost:8000/integrations/strava/callback",
    )
    monkeypatch.setattr("config.settings.secret_key", "test-secret")


def _auth_url_state(client) -> str:
    """Round-trip helper: fetch /auth and extract the signed state param."""
    url = client.get("/integrations/strava/auth").json()["url"]
    return str(parse_qs(urlparse(url).query)["state"][0])


def test_strava_auth_url_unconfigured(client):
    resp = client.get("/integrations/strava/auth")
    assert resp.status_code == 400


def test_strava_auth_url_configured(client, monkeypatch):
    _configure_strava(monkeypatch)

    resp = client.get("/integrations/strava/auth")
    assert resp.status_code == 200
    data = resp.json()
    assert "strava.com" in data["url"]
    assert "strava-client-id" in data["url"]
    # CSRF nonce must be embedded so Strava echoes it back to /callback (#1328).
    state = parse_qs(urlparse(data["url"]).query)["state"][0]
    assert oauth_state.verify_state(state, "strava") is True


def test_strava_callback_missing_code(client):
    resp = client.get("/integrations/strava/callback")
    assert resp.status_code == 400


def test_strava_callback_error(client):
    resp = client.get("/integrations/strava/callback?error=access_denied")
    assert resp.status_code == 400


def test_strava_callback_rejects_missing_state(client, monkeypatch):
    _configure_strava(monkeypatch)

    exchange = AsyncMock()
    with patch("services.strava_service.exchange_code", new=exchange):
        resp = client.get("/integrations/strava/callback?code=abc123")

    assert resp.status_code == 400
    exchange.assert_not_awaited()  # denied before any token exchange


def test_strava_callback_rejects_wrong_state(client, monkeypatch):
    _configure_strava(monkeypatch)

    exchange = AsyncMock()
    with patch("services.strava_service.exchange_code", new=exchange):
        resp = client.get("/integrations/strava/callback?code=abc123&state=forged")

    assert resp.status_code == 400
    exchange.assert_not_awaited()


def test_strava_callback_rejects_state_from_other_provider(client, monkeypatch):
    # A state legitimately signed for Spotify must not pass at Strava's callback.
    _configure_strava(monkeypatch)
    state = oauth_state.generate_state("spotify")

    exchange = AsyncMock()
    with patch("services.strava_service.exchange_code", new=exchange):
        resp = client.get(f"/integrations/strava/callback?code=abc123&state={state}")

    assert resp.status_code == 400
    exchange.assert_not_awaited()


def test_strava_callback_exchanges_code(client, monkeypatch):
    _configure_strava(monkeypatch)

    fake_response = MagicMock()
    fake_response.json.return_value = {
        "access_token": "ACCESS",
        "refresh_token": "REFRESH",
        "expires_in": 3600,
        "token_type": "Bearer",
        "athlete": {"id": 1, "firstname": "Ada"},
    }
    fake_response.raise_for_status.return_value = None

    # Full round-trip: state issued by /auth must be echoed back by Strava.
    state = _auth_url_state(client)
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        resp = client.get(f"/integrations/strava/callback?code=abc123&state={state}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] == "ACCESS"
    assert data["athlete"]["firstname"] == "Ada"


def test_strava_activities_list(client, monkeypatch):
    _configure_strava(monkeypatch)

    fake_response = MagicMock()
    fake_response.json.return_value = [{"id": 123, "name": "Morning Run"}]
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/strava/activities", headers=STRAVA_TOKEN_HEADER)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Morning Run"


def test_strava_data_endpoints_reject_query_token(client):
    # ?token= must not be accepted — Bearer credentials never travel in URLs
    # (access logs, browser history, Referer). Missing header → 422 (#1328).
    for path in ("activities", "athlete"):
        resp = client.get(f"/integrations/strava/{path}?token=xyz")
        assert resp.status_code == 422, path
