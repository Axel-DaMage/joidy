"""Tests for the Strava integration router and service (#44).

Covers the server-side token contract: the OAuth callback persists encrypted
tokens and never returns them to the browser, data endpoints resolve the
access token from ``integration_tokens`` (with transparent refresh) or the
legacy ``X-Strava-Token`` header override, and sync/webhook XP awards are
idempotent via dedup keys. All Strava HTTP calls are mocked — no network.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
from services import integration_token_service as its
from services import oauth_state
from sqlalchemy import text

STRAVA_TOKEN_HEADER = {"X-Strava-Token": "xyz"}
STRAVA_BASE = "https://www.strava.com"


def _configure_strava(monkeypatch):
    monkeypatch.setattr("services.strava_service.settings.strava_client_id", "strava-client-id")
    monkeypatch.setattr("services.strava_service.settings.strava_client_secret", "strava-client-secret")
    monkeypatch.setattr(
        "services.strava_service.settings.strava_redirect_uri",
        "http://localhost:8000/integrations/strava/callback",
    )
    monkeypatch.setattr("config.settings.secret_key", "test-secret")


def _configure_webhook(monkeypatch, token="test-verify-token"):
    monkeypatch.setattr("config.settings.strava_webhook_verify_token", token)


def _auth_url_state(client) -> str:
    """Round-trip helper: fetch /auth and extract the signed state param."""
    url = client.get("/integrations/strava/auth").json()["url"]
    return str(parse_qs(urlparse(url).query)["state"][0])


def _fake_response(payload, status_code: int = 200):
    """MagicMock mimicking an httpx.Response for the mocked AsyncClient."""
    fake = MagicMock()
    fake.json.return_value = payload
    fake.status_code = status_code
    fake.raise_for_status.return_value = None
    return fake


def _http_status_error(status_code: int, url: str = f"{STRAVA_BASE}/api/v3/athlete") -> httpx.HTTPStatusError:
    """A real httpx.HTTPStatusError so routers can map upstream statuses."""
    request = httpx.Request("GET", url)
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(f"HTTP {status_code}", request=request, response=response)


def _seed_tokens(db_session, *, access_token="STORED-ACCESS", refresh_token="STORED-REFRESH", **kwargs):
    """Persist encrypted Strava tokens the way the OAuth callback does."""
    return its.store_tokens(
        db_session,
        its.PROVIDER_STRAVA,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=kwargs.pop("expires_in", 3600),
        account_id=kwargs.pop("account_id", "12345"),
        **kwargs,
    )


def _xp_events(db_session, event_type: str):
    from models.gamification import XPEvent

    return db_session.query(XPEvent).filter(XPEvent.event_type == event_type).all()


# ---------------------------------------------------------------------------
# OAuth flow
# ---------------------------------------------------------------------------


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
    # Popup contract: errors render the self-closing HTML page (200), like Google.
    resp = client.get("/integrations/strava/callback")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "ERROR" in resp.text


def test_strava_callback_error(client):
    resp = client.get("/integrations/strava/callback?error=access_denied")
    assert resp.status_code == 200
    assert "ERROR" in resp.text


def test_strava_callback_rejects_missing_state(client, monkeypatch):
    _configure_strava(monkeypatch)

    exchange = AsyncMock()
    with patch("services.strava_service.exchange_code", new=exchange):
        resp = client.get("/integrations/strava/callback?code=abc123")

    assert resp.status_code == 403
    exchange.assert_not_awaited()  # denied before any token exchange


def test_strava_callback_rejects_wrong_state(client, monkeypatch):
    _configure_strava(monkeypatch)

    exchange = AsyncMock()
    with patch("services.strava_service.exchange_code", new=exchange):
        resp = client.get("/integrations/strava/callback?code=abc123&state=forged")

    assert resp.status_code == 403
    exchange.assert_not_awaited()


def test_strava_callback_rejects_state_from_other_provider(client, monkeypatch):
    # A state legitimately signed for Spotify must not pass at Strava's callback.
    _configure_strava(monkeypatch)
    state = oauth_state.generate_state("spotify")

    exchange = AsyncMock()
    with patch("services.strava_service.exchange_code", new=exchange):
        resp = client.get(f"/integrations/strava/callback?code=abc123&state={state}")

    assert resp.status_code == 403
    exchange.assert_not_awaited()


def test_strava_callback_stores_tokens_server_side(client, db_session, monkeypatch):
    """#44 contract: tokens are persisted encrypted, never returned to the browser."""
    _configure_strava(monkeypatch)

    fake_response = _fake_response(
        {
            "access_token": "ACCESS",
            "refresh_token": "REFRESH",
            "expires_in": 3600,
            "expires_at": 1893456000,
            "token_type": "Bearer",
            "athlete": {"id": 1, "firstname": "Ada"},
        }
    )

    # Full round-trip: state issued by /auth must be echoed back by Strava.
    state = _auth_url_state(client)
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        resp = client.get(f"/integrations/strava/callback?code=abc123&state={state}")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Strava conectado" in resp.text
    # Tokens must NOT leak into the callback response.
    assert "ACCESS" not in resp.text
    assert "REFRESH" not in resp.text
    assert "access_token" not in resp.text

    # …but they ARE stored, encrypted at rest.
    row = its.get_stored_token(db_session, its.PROVIDER_STRAVA)
    assert row is not None
    assert row.access_token == "ACCESS"  # EncryptedText decrypts transparently
    assert its.decrypt_token(row.refresh_token_encrypted) == "REFRESH"
    assert row.account_id == "1"
    assert its.is_connected(db_session, its.PROVIDER_STRAVA) is True

    raw_access = db_session.execute(
        text("SELECT access_token FROM integration_tokens WHERE provider = 'strava'")
    ).scalar()
    raw_refresh = db_session.execute(
        text("SELECT refresh_token_encrypted FROM integration_tokens WHERE provider = 'strava'")
    ).scalar()
    # Fernet ciphertext — never the plaintext token.
    assert raw_access.startswith("gAAAA")
    assert raw_refresh.startswith("gAAAA")
    assert "ACCESS" not in raw_access
    assert "REFRESH" not in raw_refresh


def test_strava_callback_exchange_failure(client, monkeypatch):
    _configure_strava(monkeypatch)
    state = _auth_url_state(client)

    fake_response = MagicMock()
    fake_response.raise_for_status.side_effect = _http_status_error(400, f"{STRAVA_BASE}/oauth/token")

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        resp = client.get(f"/integrations/strava/callback?code=abc123&state={state}")

    assert resp.status_code == 200
    assert "ERROR" in resp.text
    assert "token" not in resp.text.lower() or "intercambio" in resp.text.lower()


# ---------------------------------------------------------------------------
# Status / disconnect
# ---------------------------------------------------------------------------


def test_strava_status_not_connected(client):
    resp = client.get("/integrations/strava/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is False
    assert data["athlete"] is None


def test_strava_status_connected(client, db_session, monkeypatch):
    _configure_strava(monkeypatch)
    _seed_tokens(db_session)

    athlete = {"id": 12345, "firstname": "Ada", "lastname": "L", "username": "ada", "profile": "https://x/p.jpg"}
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_fake_response(athlete))):
        resp = client.get("/integrations/strava/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is True
    assert data["connected"] is True
    assert data["athlete"]["firstname"] == "Ada"
    # Summary must not leak tokens.
    assert "access_token" not in data["athlete"]


def test_strava_disconnect(client, db_session, monkeypatch):
    _configure_strava(monkeypatch)
    _seed_tokens(db_session)

    deauth = _fake_response({"message": "ok"})
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=deauth)) as post:
        resp = client.post("/integrations/strava/disconnect")

    assert resp.status_code == 200
    assert resp.json()["status"] == "disconnected"
    assert its.get_stored_token(db_session, its.PROVIDER_STRAVA) is None
    # Deauthorize was called with the stored access token.
    assert post.await_args.kwargs["data"]["access_token"] == "STORED-ACCESS"


def test_strava_disconnect_survives_strava_failure(client, db_session, monkeypatch):
    """Local disconnect must succeed even when Strava's deauthorize endpoint is down."""
    _configure_strava(monkeypatch)
    _seed_tokens(db_session)

    fake_response = MagicMock()
    fake_response.raise_for_status.side_effect = _http_status_error(500, f"{STRAVA_BASE}/oauth/deauthorize")

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        resp = client.post("/integrations/strava/disconnect")

    assert resp.status_code == 200
    assert its.get_stored_token(db_session, its.PROVIDER_STRAVA) is None


# ---------------------------------------------------------------------------
# Data endpoints — stored token, header override, error mapping
# ---------------------------------------------------------------------------


def test_strava_activities_list(client, monkeypatch):
    _configure_strava(monkeypatch)

    fake_response = _fake_response([{"id": 123, "name": "Morning Run"}])
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/strava/activities", headers=STRAVA_TOKEN_HEADER)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Morning Run"


def test_strava_activities_uses_stored_token(client, db_session, monkeypatch):
    """No header → the stored (auto-refreshed) token is used; ``?token=`` is ignored."""
    _configure_strava(monkeypatch)
    _seed_tokens(db_session)

    get_mock = AsyncMock(return_value=_fake_response([{"id": 1, "name": "Run"}]))
    with patch("httpx.AsyncClient.get", new=get_mock):
        resp = client.get("/integrations/strava/activities?token=SHOULD-BE-IGNORED")

    assert resp.status_code == 200
    sent_headers = get_mock.await_args.kwargs["headers"]
    assert sent_headers["Authorization"] == "Bearer STORED-ACCESS"


def test_strava_data_endpoints_require_connection(client):
    # No header and no stored token → 401 reconnect error (never a token leak).
    for path in ("activities", "athlete", "stats", "routes"):
        resp = client.get(f"/integrations/strava/{path}")
        assert resp.status_code == 401, path


def test_strava_activities_pagination_params(client, db_session, monkeypatch):
    _configure_strava(monkeypatch)
    _seed_tokens(db_session)

    get_mock = AsyncMock(return_value=_fake_response([]))
    with patch("httpx.AsyncClient.get", new=get_mock):
        resp = client.get("/integrations/strava/activities?per_page=50&page=2&before=1700000000&after=1600000000")

    assert resp.status_code == 200
    params = get_mock.await_args.kwargs["params"]
    assert params["per_page"] == 50
    assert params["page"] == 2
    assert params["before"] == 1700000000
    assert params["after"] == 1600000000


def test_strava_activities_sport_type_filter(client, db_session, monkeypatch):
    _configure_strava(monkeypatch)
    _seed_tokens(db_session)

    activities = [
        {"id": 1, "name": "Trail", "sport_type": "TrailRun"},
        {"id": 2, "name": "Bike", "sport_type": "MountainBikeRide"},
        {"id": 3, "name": "Swim", "sport_type": "Swim"},
    ]
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_fake_response(activities))):
        resp = client.get("/integrations/strava/activities?sport_type=ride")

    assert resp.status_code == 200
    names = [a["name"] for a in resp.json()]
    assert names == ["Bike"]  # substring match, case-insensitive


def test_strava_activity_detail(client, db_session, monkeypatch):
    _configure_strava(monkeypatch)
    _seed_tokens(db_session)

    detail = {"id": 42, "name": "Long Ride", "map": {"polyline": "abc"}, "splits_metric": [{"distance": 1000}]}
    get_mock = AsyncMock(return_value=_fake_response(detail))
    with patch("httpx.AsyncClient.get", new=get_mock):
        resp = client.get("/integrations/strava/activities/42")

    assert resp.status_code == 200
    assert resp.json()["id"] == 42
    assert "splits_metric" in resp.json()
    assert "/activities/42" in get_mock.await_args.args[0]


def test_strava_activity_streams(client, db_session, monkeypatch):
    _configure_strava(monkeypatch)
    _seed_tokens(db_session)

    streams = [{"type": "time", "data": [0, 1, 2]}, {"type": "latlng", "data": [[1, 2]]}]
    get_mock = AsyncMock(return_value=_fake_response(streams))
    with patch("httpx.AsyncClient.get", new=get_mock):
        resp = client.get("/integrations/strava/activities/42/streams?keys=time,latlng")

    assert resp.status_code == 200
    assert resp.json()[0]["type"] == "time"
    params = get_mock.await_args.kwargs["params"]
    assert params["keys"] == "time,latlng"
    assert params["key_by_type"] == "true"


def test_strava_stats_uses_stored_account_id(client, db_session, monkeypatch):
    _configure_strava(monkeypatch)
    _seed_tokens(db_session, account_id="12345")

    stats = {"biggest_ride_distance": 50000, "recent_run_totals": {"count": 3}}
    get_mock = AsyncMock(return_value=_fake_response(stats))
    with patch("httpx.AsyncClient.get", new=get_mock):
        resp = client.get("/integrations/strava/stats")

    assert resp.status_code == 200
    assert resp.json()["recent_run_totals"]["count"] == 3
    # Stored athlete id avoids the extra /athlete lookup.
    assert "/athletes/12345/stats" in get_mock.await_args.args[0]


def test_strava_routes(client, db_session, monkeypatch):
    _configure_strava(monkeypatch)
    _seed_tokens(db_session)

    routes = [{"id": 7, "name": "Morning Loop", "distance": 10000}]
    get_mock = AsyncMock(return_value=_fake_response(routes))
    with patch("httpx.AsyncClient.get", new=get_mock):
        resp = client.get("/integrations/strava/routes?per_page=10&page=1")

    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "Morning Loop"
    params = get_mock.await_args.kwargs["params"]
    assert params["per_page"] == 10
    assert params["page"] == 1


def test_strava_upstream_401_maps_to_reconnect(client, db_session, monkeypatch):
    _configure_strava(monkeypatch)
    _seed_tokens(db_session)

    fake_response = MagicMock()
    fake_response.raise_for_status.side_effect = _http_status_error(401)
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/strava/activities")

    assert resp.status_code == 401
    assert "reconecta" in resp.json()["detail"].lower()


def test_strava_upstream_429_maps(client, db_session, monkeypatch):
    _configure_strava(monkeypatch)
    _seed_tokens(db_session)

    fake_response = MagicMock()
    fake_response.raise_for_status.side_effect = _http_status_error(429)
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/strava/activities")

    assert resp.status_code == 429


def test_strava_upstream_500_maps_to_502(client, db_session, monkeypatch):
    _configure_strava(monkeypatch)
    _seed_tokens(db_session)

    fake_response = MagicMock()
    fake_response.raise_for_status.side_effect = _http_status_error(500)
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/strava/activities")

    assert resp.status_code == 502


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------


def test_strava_expired_token_refreshes_and_rotates(client, db_session, monkeypatch):
    """Strava rotates refresh tokens — the new one must replace the stored one."""
    _configure_strava(monkeypatch)
    _seed_tokens(db_session, expires_in=-100)  # already expired

    refresh_payload = {
        "access_token": "NEW-ACCESS",
        "refresh_token": "NEW-REFRESH",
        "expires_in": 3600,
        "expires_at": 1893456000,
        "token_type": "Bearer",
        "athlete": {"id": 12345},
    }
    post_mock = AsyncMock(return_value=_fake_response(refresh_payload))
    get_mock = AsyncMock(return_value=_fake_response([{"id": 1, "name": "Run"}]))

    with (
        patch("httpx.AsyncClient.post", new=post_mock),
        patch("httpx.AsyncClient.get", new=get_mock),
    ):
        resp = client.get("/integrations/strava/activities")

    assert resp.status_code == 200
    # Refresh call hit the token endpoint with the OLD refresh token.
    post_call = post_mock.await_args
    assert post_call.kwargs["data"]["grant_type"] == "refresh_token"
    assert post_call.kwargs["data"]["refresh_token"] == "STORED-REFRESH"
    # The API call used the NEW access token.
    assert get_mock.await_args.kwargs["headers"]["Authorization"] == "Bearer NEW-ACCESS"
    # Rotated refresh token persisted (encrypted).
    row = its.get_stored_token(db_session, its.PROVIDER_STRAVA)
    assert row.access_token == "NEW-ACCESS"
    assert its.decrypt_token(row.refresh_token_encrypted) == "NEW-REFRESH"
    assert row.account_id == "12345"


def test_strava_refresh_failure_returns_401(client, db_session, monkeypatch):
    _configure_strava(monkeypatch)
    _seed_tokens(db_session, expires_in=-100)

    fake_response = MagicMock()
    fake_response.raise_for_status.side_effect = _http_status_error(400, f"{STRAVA_BASE}/oauth/token")

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/strava/activities")

    assert resp.status_code == 401
    assert "conectar" in resp.json()["detail"].lower()


def test_strava_valid_token_skips_refresh(client, db_session, monkeypatch):
    _configure_strava(monkeypatch)
    _seed_tokens(db_session, expires_in=3600)

    post_mock = AsyncMock()
    get_mock = AsyncMock(return_value=_fake_response([]))
    with (
        patch("httpx.AsyncClient.post", new=post_mock),
        patch("httpx.AsyncClient.get", new=get_mock),
    ):
        resp = client.get("/integrations/strava/activities")

    assert resp.status_code == 200
    post_mock.assert_not_awaited()  # no refresh needed


# ---------------------------------------------------------------------------
# Sync + gamification
# ---------------------------------------------------------------------------


def _activity(activity_id: int, name: str = "Run", sport_type: str = "Run", start_date: str = "2026-11-18T08:00:00Z"):
    return {
        "id": activity_id,
        "name": name,
        "sport_type": sport_type,
        "type": sport_type,
        "start_date": start_date,
        "distance": 10000.0,
        "moving_time": 3600,
    }


def test_strava_sync_awards_xp_idempotent(client, db_session, monkeypatch):
    _configure_strava(monkeypatch)
    _seed_tokens(db_session)

    # Activities in two different ISO weeks (2026-11-15 → W46, 2026-11-18 → W47).
    page1 = [_activity(101, "Morning"), _activity(102, "Evening", start_date="2026-11-15T18:00:00Z")]
    responses = [_fake_response(page1), _fake_response([])]  # page 2 empty → stop

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=responses)):
        resp = client.post("/integrations/strava/sync")

    assert resp.status_code == 200
    data = resp.json()
    assert data["fetched"] == 2
    assert data["new"] == 2
    assert data["weeks"] == ["2026-W46", "2026-W47"]

    # One XPEvent per activity + one weekly bonus per ISO week.
    activity_events = _xp_events(db_session, "strava_activity")
    assert {e.dedup_key for e in activity_events} == {"strava:activity:101", "strava:activity:102"}
    week_events = _xp_events(db_session, "strava_weekly_bonus")
    assert {e.dedup_key for e in week_events} == {"strava:week:2026-W46", "strava:week:2026-W47"}

    # Re-sync: same activities → zero new awards, no duplicate XPEvents.
    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=[_fake_response(page1)])):
        resp2 = client.post("/integrations/strava/sync")

    assert resp2.status_code == 200
    assert resp2.json()["new"] == 0
    assert resp2.json()["xp_awarded"] == 0
    assert len(_xp_events(db_session, "strava_activity")) == 2
    assert len(_xp_events(db_session, "strava_weekly_bonus")) == 2


def test_strava_sync_requires_connection(client):
    resp = client.post("/integrations/strava/sync")
    assert resp.status_code == 401


def test_strava_sync_upstream_401(client, db_session, monkeypatch):
    _configure_strava(monkeypatch)
    _seed_tokens(db_session)

    fake_response = MagicMock()
    fake_response.raise_for_status.side_effect = _http_status_error(401, f"{STRAVA_BASE}/api/v3/athlete/activities")
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=fake_response)):
        resp = client.post("/integrations/strava/sync")

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Webhook (public, verify-token protected, disabled unless configured)
# ---------------------------------------------------------------------------


def test_strava_webhook_disabled_by_default(client, monkeypatch):
    # Empty verify token → both webhook routes are off (404), JWT-free or not.
    _configure_webhook(monkeypatch, token="")

    resp_get = client.get("/integrations/strava/webhook")
    resp_post = client.post("/integrations/strava/webhook", json={})
    assert resp_get.status_code == 404
    assert resp_post.status_code == 404


def test_strava_webhook_verify_handshake(client, monkeypatch):
    _configure_webhook(monkeypatch)

    resp = client.get(
        "/integrations/strava/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "test-verify-token", "hub.challenge": "abc123"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"hub.challenge": "abc123"}


def test_strava_webhook_verify_rejects_wrong_token(client, monkeypatch):
    _configure_webhook(monkeypatch)

    resp = client.get(
        "/integrations/strava/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "abc123"},
    )
    assert resp.status_code == 403


def test_strava_webhook_verify_rejects_bad_mode(client, monkeypatch):
    _configure_webhook(monkeypatch)

    resp = client.get(
        "/integrations/strava/webhook",
        params={"hub.mode": "unsubscribe", "hub.verify_token": "test-verify-token", "hub.challenge": "abc123"},
    )
    assert resp.status_code == 403


def test_strava_webhook_event_awards_xp_idempotent(client, db_session, monkeypatch):
    _configure_strava(monkeypatch)
    _configure_webhook(monkeypatch)
    _seed_tokens(db_session, account_id="12345")

    activity = _activity(555, "Webhook Run", start_date="2026-11-18T09:00:00Z")
    event = {"object_type": "activity", "aspect_type": "create", "object_id": 555, "owner_id": 12345}

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_fake_response(activity))):
        resp = client.post("/integrations/strava/webhook", json=event)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["awarded"] is True
    assert data["weekly_bonus"] is True

    events = _xp_events(db_session, "strava_activity")
    assert [e.dedup_key for e in events] == ["strava:activity:555"]
    week_events = _xp_events(db_session, "strava_weekly_bonus")
    assert [e.dedup_key for e in week_events] == ["strava:week:2026-W47"]

    # Replay (Strava retries deliveries) → no double award.
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_fake_response(activity))):
        resp2 = client.post("/integrations/strava/webhook", json=event)

    assert resp2.status_code == 200
    assert resp2.json()["awarded"] is False
    assert resp2.json()["weekly_bonus"] is False
    assert len(_xp_events(db_session, "strava_activity")) == 1


def test_strava_webhook_ignores_foreign_owner(client, db_session, monkeypatch):
    """Events for other athletes' activities must not award XP."""
    _configure_strava(monkeypatch)
    _configure_webhook(monkeypatch)
    _seed_tokens(db_session, account_id="12345")

    event = {"object_type": "activity", "aspect_type": "create", "object_id": 777, "owner_id": 99999}
    resp = client.post("/integrations/strava/webhook", json=event)

    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
    assert resp.json()["reason"] == "owner_mismatch"
    assert _xp_events(db_session, "strava_activity") == []


def test_strava_webhook_ignores_non_activity_events(client, db_session, monkeypatch):
    _configure_strava(monkeypatch)
    _configure_webhook(monkeypatch)
    _seed_tokens(db_session)

    for event in (
        {"object_type": "athlete", "aspect_type": "create", "object_id": 1, "owner_id": 12345},
        {"object_type": "activity", "aspect_type": "update", "object_id": 1, "owner_id": 12345},
        {"object_type": "activity", "aspect_type": "delete", "object_id": 1, "owner_id": 12345},
    ):
        resp = client.post("/integrations/strava/webhook", json=event)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"


def test_strava_webhook_not_connected(client, monkeypatch):
    _configure_webhook(monkeypatch)

    event = {"object_type": "activity", "aspect_type": "create", "object_id": 1, "owner_id": 1}
    resp = client.post("/integrations/strava/webhook", json=event)
    assert resp.status_code == 200
    assert resp.json()["reason"] == "not_connected"


def test_strava_webhook_rejects_invalid_json(client, monkeypatch):
    _configure_webhook(monkeypatch)

    resp = client.post(
        "/integrations/strava/webhook",
        content=b"not-json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400
