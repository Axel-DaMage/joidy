"""Tests for Google integration router and service."""

from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

from services import google_token_service as gts
from services import oauth_state


def _configure_google(monkeypatch):
    monkeypatch.setattr("services.google_service.settings.google_client_id", "google-client-id")
    monkeypatch.setattr("services.google_service.settings.google_client_secret", "google-client-secret")
    monkeypatch.setattr(
        "services.google_service.settings.google_redirect_uri",
        "http://localhost:8000/integrations/google/callback",
    )
    monkeypatch.setattr("config.settings.secret_key", "test-secret")


def _auth_url_state(client) -> str:
    """Round-trip helper: fetch /auth and extract the signed state param."""
    url = client.get("/integrations/google/auth").json()["url"]
    return str(parse_qs(urlparse(url).query)["state"][0])


def test_google_auth_url_unconfigured(client):
    resp = client.get("/integrations/google/auth")
    assert resp.status_code == 400


def test_google_auth_url_configured(client, monkeypatch):
    _configure_google(monkeypatch)

    resp = client.get("/integrations/google/auth")
    assert resp.status_code == 200
    data = resp.json()
    assert "accounts.google.com" in data["url"]
    assert "google-client-id" in data["url"]
    # CSRF nonce must be embedded so Google echoes it back to /callback (#1280).
    state = parse_qs(urlparse(data["url"]).query)["state"][0]
    assert oauth_state.verify_state(state, "google") is True


def test_google_callback_missing_code(client):
    # The callback returns a self-closing HTML page (popup UX) instead of JSON:
    # a browser redirect hits it without credentials.
    resp = client.get("/integrations/google/callback")
    assert resp.status_code == 200
    assert "ERROR" in resp.text
    assert "Código" in resp.text or "código" in resp.text


def test_google_callback_error(client):
    resp = client.get("/integrations/google/callback?error=access_denied")
    assert resp.status_code == 200
    assert "ERROR" in resp.text
    # Generic message — no raw provider details leak to the browser
    assert "Error de autorización" in resp.text
    assert "access_denied" not in resp.text


def test_google_callback_rejects_missing_state(client, monkeypatch):
    _configure_google(monkeypatch)

    exchange = AsyncMock()
    with patch("services.google_service.exchange_code", new=exchange):
        resp = client.get("/integrations/google/callback?code=abc123")

    assert resp.status_code == 403
    assert "ERROR" in resp.text
    exchange.assert_not_awaited()


def test_google_callback_rejects_wrong_state(client, monkeypatch):
    _configure_google(monkeypatch)

    exchange = AsyncMock()
    with patch("services.google_service.exchange_code", new=exchange):
        resp = client.get("/integrations/google/callback?code=abc123&state=forged")

    assert resp.status_code == 403
    assert "ERROR" in resp.text
    exchange.assert_not_awaited()


def test_google_callback_rejects_state_from_other_provider(client, monkeypatch):
    # A state legitimately signed for GitHub must not pass at Google's callback.
    _configure_google(monkeypatch)
    state = oauth_state.generate_state("github")

    exchange = AsyncMock()
    with patch("services.google_service.exchange_code", new=exchange):
        resp = client.get(f"/integrations/google/callback?code=abc123&state={state}")

    assert resp.status_code == 403
    exchange.assert_not_awaited()


def test_google_callback_exchanges_code(client, monkeypatch):
    _configure_google(monkeypatch)

    fake_response = MagicMock()
    fake_response.json.return_value = {
        "access_token": "ACCESS",
        "refresh_token": "REFRESH",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "calendar tasks",
    }
    fake_response.raise_for_status.return_value = None

    # Full round-trip: state issued by /auth must be echoed back by Google.
    state = _auth_url_state(client)
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        resp = client.get(f"/integrations/google/callback?code=abc123&state={state}")

    # Tokens are persisted server-side and the page confirms success
    assert resp.status_code == 200
    assert "OK" in resp.text

    resp = client.get("/integrations/google/status")
    assert resp.json()["connected"] is True


def test_google_status_not_connected(client):
    resp = client.get("/integrations/google/status")
    assert resp.status_code == 200
    assert resp.json()["connected"] is False


def test_google_connect_persists_tokens(client, db_session, monkeypatch):
    monkeypatch.setattr("services.google_service.settings.google_client_id", "google-client-id")
    monkeypatch.setattr("services.google_service.settings.google_client_secret", "google-client-secret")
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
        resp = client.post("/integrations/google/connect", json={"code": "abc123"})

    assert resp.status_code == 200
    assert resp.json()["status"] == "connected"

    # Verify status now shows connected
    resp = client.get("/integrations/google/status")
    assert resp.json()["connected"] is True


def test_google_disconnect_clears_tokens(client, db_session, monkeypatch):
    # First connect
    monkeypatch.setattr("services.google_service.settings.google_client_id", "google-client-id")
    monkeypatch.setattr("services.google_service.settings.google_client_secret", "google-client-secret")
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
        client.post("/integrations/google/connect", json={"code": "abc123"})

    # Now disconnect
    resp = client.post("/integrations/google/disconnect")
    assert resp.status_code == 200
    assert resp.json()["status"] == "disconnected"

    # Verify status shows not connected
    resp = client.get("/integrations/google/status")
    assert resp.json()["connected"] is False


def test_google_token_service_encrypt_decrypt(db_session):
    """Test that token encryption/decryption round-trips correctly."""
    encrypted = gts.encrypt_token("my-secret-token")
    assert encrypted != "my-secret-token"
    decrypted = gts.decrypt_token(encrypted)
    assert decrypted == "my-secret-token"


def test_google_token_service_store_and_retrieve(db_session):
    """Test storing and retrieving tokens from the database."""
    row = gts.store_tokens(
        db_session,
        access_token="ACCESS123",
        refresh_token="REFRESH456",
        expires_in=3600,
        token_type="Bearer",
        scope="calendar tasks",
    )
    assert row.access_token == "ACCESS123"
    assert row.refresh_token_encrypted is not None
    assert row.refresh_token_encrypted != "REFRESH456"

    retrieved = gts.get_stored_token(db_session)
    assert retrieved is not None
    assert retrieved.access_token == "ACCESS123"

    assert gts.is_connected(db_session) is True


def test_google_token_service_clear_tokens(db_session):
    """Test clearing tokens from the database."""
    gts.store_tokens(
        db_session,
        access_token="ACCESS",
        refresh_token="REFRESH",
        expires_in=3600,
    )
    assert gts.is_connected(db_session) is True

    gts.clear_tokens(db_session)
    assert gts.is_connected(db_session) is False
    assert gts.get_stored_token(db_session) is None


def test_google_calendars_list(client, monkeypatch):
    monkeypatch.setattr("services.google_service.settings.google_client_id", "google-client-id")
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
    monkeypatch.setattr("services.google_service.settings.google_client_id", "google-client-id")
    monkeypatch.setattr(
        "services.google_service.settings.google_redirect_uri",
        "http://localhost:8000/integrations/google/callback",
    )

    fake_response = MagicMock()
    fake_response.json.return_value = {"messages": [{"id": "msg1", "threadId": "t1"}]}
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/google/gmail?token=xyz&max_results=5")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "msg1"


def test_google_contacts_list(client, monkeypatch):
    monkeypatch.setattr("services.google_service.settings.google_client_id", "google-client-id")
    monkeypatch.setattr(
        "services.google_service.settings.google_redirect_uri",
        "http://localhost:8000/integrations/google/callback",
    )

    fake_response = MagicMock()
    fake_response.json.return_value = {"connections": [{"resourceName": "people/1", "names": [{"displayName": "Ada"}]}]}
    fake_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/google/contacts?token=xyz&page_size=10")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["resourceName"] == "people/1"
