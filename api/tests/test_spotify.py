"""Tests for the Spotify integration router and service (#45).

Covers the server-side token contract (shared with Strava via
``integration_token_service``): the OAuth callback persists encrypted tokens
and never returns them to the browser, data endpoints resolve the access
token from ``integration_tokens`` (with transparent refresh) or the legacy
``X-Spotify-Token`` header override, responses are normalized to the
frontend's snake_case shape, and Spotify's Premium gating (403/404) maps to
clear errors. All Spotify HTTP calls are mocked — no network.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
from services import integration_token_service as its
from services import oauth_state
from sqlalchemy import text

SPOTIFY_TOKEN_HEADER = {"X-Spotify-Token": "xyz"}
SPOTIFY_API_BASE = "https://api.spotify.com/v1"


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
    url = client.get("/integrations/spotify/auth").json()["url"]
    return str(parse_qs(urlparse(url).query)["state"][0])


def _fake_response(payload, status_code: int = 200):
    """MagicMock mimicking an httpx.Response for the mocked AsyncClient."""
    fake = MagicMock()
    fake.json.return_value = payload
    fake.status_code = status_code
    fake.raise_for_status.return_value = None
    return fake


def _http_status_error(status_code: int, url: str = f"{SPOTIFY_API_BASE}/me/player") -> httpx.HTTPStatusError:
    """A real httpx.HTTPStatusError so routers can map upstream statuses."""
    request = httpx.Request("GET", url)
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(f"HTTP {status_code}", request=request, response=response)


def _seed_tokens(db_session, *, access_token="STORED-ACCESS", refresh_token="STORED-REFRESH", **kwargs):
    """Persist encrypted Spotify tokens the way the OAuth callback does."""
    return its.store_tokens(
        db_session,
        its.PROVIDER_SPOTIFY,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=kwargs.pop("expires_in", 3600),
        account_id=kwargs.pop("account_id", "spotify-user-1"),
        **kwargs,
    )


def _track_payload(name: str = "Song", track_id: str = "track1") -> dict:
    return {
        "id": track_id,
        "uri": f"spotify:track:{track_id}",
        "name": name,
        "artists": [{"id": "artist1", "name": "Artist One", "uri": "spotify:artist:artist1"}],
        "album": {
            "id": "album1",
            "name": "Album One",
            "uri": "spotify:album:album1",
            "images": [{"url": "https://img/large.jpg", "width": 640}, {"url": "https://img/small.jpg"}],
        },
        "duration_ms": 200000,
        "explicit": False,
        "preview_url": "https://preview/1.mp3",
        "is_playable": True,
    }


def _playback_state_payload() -> dict:
    return {
        "is_playing": True,
        "progress_ms": 45000,
        "shuffle_state": False,
        "repeat_state": "off",
        "item": _track_payload("Now Playing Song"),
        "context": {"type": "playlist", "uri": "spotify:playlist:pl1", "metadata": {"name": "My Mix"}},
        "device": {
            "id": "dev1",
            "name": "Kitchen Speaker",
            "type": "Computer",
            "is_active": True,
            "volume_percent": 55,
        },
    }


# ---------------------------------------------------------------------------
# OAuth flow
# ---------------------------------------------------------------------------


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
    query = parse_qs(urlparse(data["url"]).query)
    # CSRF nonce must be embedded so Spotify echoes it back to /callback (#1328).
    state = query["state"][0]
    assert oauth_state.verify_state(state, "spotify") is True
    # Scopes cover every endpoint in the issue: playback read+write, recently
    # played, top, playlists, profile.
    scope = query["scope"][0]
    for required in (
        "user-read-private",
        "user-read-email",
        "user-read-playback-state",
        "user-modify-playback-state",
        "user-read-recently-played",
        "user-top-read",
        "playlist-read-private",
    ):
        assert required in scope


def test_spotify_callback_missing_code(client):
    # Popup contract: errors render the self-closing HTML page (200), like Google/Strava.
    resp = client.get("/integrations/spotify/callback")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "ERROR" in resp.text


def test_spotify_callback_error(client):
    resp = client.get("/integrations/spotify/callback?error=access_denied")
    assert resp.status_code == 200
    assert "ERROR" in resp.text


def test_spotify_callback_rejects_missing_state(client, monkeypatch):
    _configure_spotify(monkeypatch)

    exchange = AsyncMock()
    with patch("services.spotify_service.exchange_code", new=exchange):
        resp = client.get("/integrations/spotify/callback?code=abc123")

    assert resp.status_code == 403
    assert "text/html" in resp.headers["content-type"]
    exchange.assert_not_awaited()  # denied before any token exchange


def test_spotify_callback_rejects_wrong_state(client, monkeypatch):
    _configure_spotify(monkeypatch)

    exchange = AsyncMock()
    with patch("services.spotify_service.exchange_code", new=exchange):
        resp = client.get("/integrations/spotify/callback?code=abc123&state=forged")

    assert resp.status_code == 403
    exchange.assert_not_awaited()


def test_spotify_callback_rejects_state_from_other_provider(client, monkeypatch):
    # A state legitimately signed for Strava must not pass at Spotify's callback.
    _configure_spotify(monkeypatch)
    state = oauth_state.generate_state("strava")

    exchange = AsyncMock()
    with patch("services.spotify_service.exchange_code", new=exchange):
        resp = client.get(f"/integrations/spotify/callback?code=abc123&state={state}")

    assert resp.status_code == 403
    exchange.assert_not_awaited()


def test_spotify_callback_stores_tokens_server_side(client, db_session, monkeypatch):
    """#45 contract: tokens are persisted encrypted, never returned to the browser."""
    _configure_spotify(monkeypatch)

    token_response = _fake_response(
        {
            "access_token": "ACCESS",
            "refresh_token": "REFRESH",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "user-read-playback-state",
        }
    )
    profile_response = _fake_response({"id": "spotify-user-42", "display_name": "Ada", "email": "ada@x.com"})

    # Full round-trip: state issued by /auth must be echoed back by Spotify.
    state = _auth_url_state(client)
    with (
        patch("httpx.AsyncClient.post", new=AsyncMock(return_value=token_response)) as post,
        patch("httpx.AsyncClient.request", new=AsyncMock(return_value=profile_response)) as request,
    ):
        resp = client.get(f"/integrations/spotify/callback?code=abc123&state={state}")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Spotify conectado" in resp.text
    # Tokens must NOT leak into the callback response.
    assert "ACCESS" not in resp.text
    assert "REFRESH" not in resp.text
    assert "access_token" not in resp.text

    # The code exchange hit the token endpoint with Basic client auth.
    post_call = post.await_args
    assert "accounts.spotify.com/api/token" in post_call.args[0]
    assert post_call.kwargs["data"]["grant_type"] == "authorization_code"
    assert post_call.kwargs["data"]["code"] == "abc123"
    # A best-effort /me fetch captured the account id.
    assert request.await_args.args[0] == "GET"
    assert request.await_args.args[1].endswith("/me")

    # …but tokens ARE stored, encrypted at rest.
    row = its.get_stored_token(db_session, its.PROVIDER_SPOTIFY)
    assert row is not None
    assert row.access_token == "ACCESS"  # EncryptedText decrypts transparently
    assert its.decrypt_token(row.refresh_token_encrypted) == "REFRESH"
    assert row.account_id == "spotify-user-42"
    assert row.scope == "user-read-playback-state"
    assert its.is_connected(db_session, its.PROVIDER_SPOTIFY) is True

    raw_access = db_session.execute(
        text("SELECT access_token FROM integration_tokens WHERE provider = 'spotify'")
    ).scalar()
    raw_refresh = db_session.execute(
        text("SELECT refresh_token_encrypted FROM integration_tokens WHERE provider = 'spotify'")
    ).scalar()
    # Fernet ciphertext — never the plaintext token.
    assert raw_access.startswith("gAAAA")
    assert raw_refresh.startswith("gAAAA")
    assert "ACCESS" not in raw_access
    assert "REFRESH" not in raw_refresh


def test_spotify_callback_profile_failure_still_connects(client, db_session, monkeypatch):
    """The /me profile fetch is cosmetic — its failure must not break OAuth."""
    _configure_spotify(monkeypatch)

    token_response = _fake_response(
        {"access_token": "ACCESS", "refresh_token": "REFRESH", "expires_in": 3600, "token_type": "Bearer"}
    )
    state = _auth_url_state(client)

    request_mock = AsyncMock(side_effect=RuntimeError("profile endpoint down"))
    with (
        patch("httpx.AsyncClient.post", new=AsyncMock(return_value=token_response)),
        patch("httpx.AsyncClient.request", new=request_mock),
    ):
        resp = client.get(f"/integrations/spotify/callback?code=abc123&state={state}")

    assert resp.status_code == 200
    assert "Spotify conectado" in resp.text
    row = its.get_stored_token(db_session, its.PROVIDER_SPOTIFY)
    assert row is not None
    assert row.account_id is None  # profile unavailable → no account id, tokens still stored


def test_spotify_callback_exchange_failure(client, monkeypatch):
    _configure_spotify(monkeypatch)
    state = _auth_url_state(client)

    fake_response = MagicMock()
    fake_response.raise_for_status.side_effect = _http_status_error(400, "https://accounts.spotify.com/api/token")

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        resp = client.get(f"/integrations/spotify/callback?code=abc123&state={state}")

    assert resp.status_code == 200
    assert "ERROR" in resp.text


# ---------------------------------------------------------------------------
# Status / disconnect
# ---------------------------------------------------------------------------


def test_spotify_status_not_connected(client):
    resp = client.get("/integrations/spotify/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is False
    assert data["connected"] is False
    assert data["account"] is None


def test_spotify_status_connected(client, db_session, monkeypatch):
    _configure_spotify(monkeypatch)
    _seed_tokens(db_session)

    profile = {"id": "spotify-user-1", "display_name": "Ada Lovelace", "email": "ada@x.com"}
    with patch("httpx.AsyncClient.request", new=AsyncMock(return_value=_fake_response(profile))):
        resp = client.get("/integrations/spotify/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is True
    assert data["connected"] is True
    assert data["account"]["display_name"] == "Ada Lovelace"
    # Summary must not leak tokens.
    assert "access_token" not in data["account"]
    assert "refresh_token" not in data["account"]


def test_spotify_disconnect(client, db_session, monkeypatch):
    """Spotify has no revocation endpoint — disconnect deletes the stored row
    and makes NO upstream call; remaining access tokens self-expire."""
    _configure_spotify(monkeypatch)
    _seed_tokens(db_session)

    post_mock = AsyncMock()
    request_mock = AsyncMock()
    with (
        patch("httpx.AsyncClient.post", new=post_mock),
        patch("httpx.AsyncClient.request", new=request_mock),
    ):
        resp = client.post("/integrations/spotify/disconnect")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "disconnected"
    assert "spotify.com/account/apps" in data["manage_apps_url"]
    assert its.get_stored_token(db_session, its.PROVIDER_SPOTIFY) is None
    post_mock.assert_not_awaited()
    request_mock.assert_not_awaited()


def test_spotify_disconnect_when_not_connected(client):
    resp = client.post("/integrations/spotify/disconnect")
    assert resp.status_code == 200
    assert resp.json()["status"] == "disconnected"


# ---------------------------------------------------------------------------
# Data endpoints — stored token, header override, normalization
# ---------------------------------------------------------------------------


def test_spotify_currently_playing_normalized(client, db_session, monkeypatch):
    _configure_spotify(monkeypatch)
    _seed_tokens(db_session)

    with patch("httpx.AsyncClient.request", new=AsyncMock(return_value=_fake_response(_playback_state_payload()))):
        resp = client.get("/integrations/spotify/currently-playing")

    assert resp.status_code == 200
    data = resp.json()
    assert data["is_playing"] is True
    assert data["progress_ms"] == 45000
    assert data["duration_ms"] == 200000
    assert data["track"]["name"] == "Now Playing Song"
    assert data["track"]["artist_names"] == "Artist One"
    assert data["track"]["album_name"] == "Album One"
    assert data["track"]["album_image_url"] == "https://img/large.jpg"
    assert data["track"]["duration_ms"] == 200000
    assert data["track"]["artists"][0]["name"] == "Artist One"
    assert data["device"]["name"] == "Kitchen Speaker"
    assert data["context"]["name"] == "My Mix"
    assert data["repeat_state"] == "off"


def test_spotify_currently_playing_nothing_playing(client, db_session, monkeypatch):
    """Spotify's 204 No Content normalizes to a stable ``is_playing: false`` shape."""
    _configure_spotify(monkeypatch)
    _seed_tokens(db_session)

    with patch("httpx.AsyncClient.request", new=AsyncMock(return_value=_fake_response({}, status_code=204))):
        resp = client.get("/integrations/spotify/currently-playing")

    assert resp.status_code == 200
    data = resp.json()
    assert data["is_playing"] is False
    assert data["track"] is None
    assert data["device"] is None
    assert data["progress_ms"] == 0


def test_spotify_recently_played(client, db_session, monkeypatch):
    _configure_spotify(monkeypatch)
    _seed_tokens(db_session)

    payload = {
        "items": [
            {"played_at": "2026-01-01T10:00:00Z", "track": _track_payload("Song 1")},
            {"played_at": "2026-01-01T09:00:00Z", "track": _track_payload("Song 2", "track2")},
        ]
    }
    request_mock = AsyncMock(return_value=_fake_response(payload))
    with patch("httpx.AsyncClient.request", new=request_mock):
        resp = client.get("/integrations/spotify/recently-played?limit=10")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["played_at"] == "2026-01-01T10:00:00Z"
    assert data[0]["track"]["name"] == "Song 1"
    assert data[1]["track"]["name"] == "Song 2"
    assert request_mock.await_args.kwargs["params"]["limit"] == 10


def test_spotify_top_artists(client, db_session, monkeypatch):
    _configure_spotify(monkeypatch)
    _seed_tokens(db_session)

    artist = {
        "id": "artist1",
        "uri": "spotify:artist:artist1",
        "name": "Artist One",
        "images": [{"url": "https://img/artist.jpg"}],
        "genres": ["rock"],
        "followers": {"total": 1234},
        "popularity": 88,
    }
    request_mock = AsyncMock(return_value=_fake_response({"items": [artist]}))
    with patch("httpx.AsyncClient.request", new=request_mock):
        resp = client.get("/integrations/spotify/top-artists?time_range=short_term&limit=5")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Artist One"
    assert data[0]["image_url"] == "https://img/artist.jpg"
    assert data[0]["genres"] == ["rock"]
    params = request_mock.await_args.kwargs["params"]
    assert params["time_range"] == "short_term"
    assert params["limit"] == 5
    assert "/me/top/artists" in request_mock.await_args.args[1]


def test_spotify_top_tracks(client, db_session, monkeypatch):
    _configure_spotify(monkeypatch)
    _seed_tokens(db_session)

    request_mock = AsyncMock(return_value=_fake_response({"items": [_track_payload("Top Song")]}))
    with patch("httpx.AsyncClient.request", new=request_mock):
        resp = client.get("/integrations/spotify/top-tracks?time_range=long_term")

    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["name"] == "Top Song"
    params = request_mock.await_args.kwargs["params"]
    assert params["time_range"] == "long_term"
    assert params["limit"] == 20  # default
    assert "/me/top/tracks" in request_mock.await_args.args[1]


def test_spotify_top_tracks_invalid_time_range_falls_back(client, db_session, monkeypatch):
    _configure_spotify(monkeypatch)
    _seed_tokens(db_session)

    request_mock = AsyncMock(return_value=_fake_response({"items": []}))
    with patch("httpx.AsyncClient.request", new=request_mock):
        resp = client.get("/integrations/spotify/top-tracks?time_range=bogus")

    assert resp.status_code == 200
    assert request_mock.await_args.kwargs["params"]["time_range"] == "medium_term"


def test_spotify_playlists(client, db_session, monkeypatch):
    _configure_spotify(monkeypatch)
    _seed_tokens(db_session)

    playlist = {
        "id": "pl1",
        "uri": "spotify:playlist:pl1",
        "name": "My Mix",
        "description": "desc",
        "images": [{"url": "https://img/pl.jpg"}],
        "owner": {"id": "spotify-user-1", "display_name": "Ada"},
        "tracks": {"total": 42},
        "public": False,
        "collaborative": False,
        "external_urls": {"spotify": "https://open.spotify.com/playlist/pl1"},
    }
    request_mock = AsyncMock(return_value=_fake_response({"items": [playlist]}))
    with patch("httpx.AsyncClient.request", new=request_mock):
        resp = client.get("/integrations/spotify/playlists?limit=10&offset=20")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "My Mix"
    assert data[0]["tracks_count"] == 42
    assert data[0]["image_url"] == "https://img/pl.jpg"
    assert data[0]["owner"]["display_name"] == "Ada"
    assert data[0]["external_url"].endswith("/pl1")
    params = request_mock.await_args.kwargs["params"]
    assert params["limit"] == 10
    assert params["offset"] == 20
    assert "/me/playlists" in request_mock.await_args.args[1]


def test_spotify_playlist_detail(client, db_session, monkeypatch):
    _configure_spotify(monkeypatch)
    _seed_tokens(db_session)

    playlist = {
        "id": "pl1",
        "uri": "spotify:playlist:pl1",
        "name": "My Mix",
        "owner": {"id": "u", "display_name": "Ada"},
        "tracks": {"total": 2, "items": [{"track": _track_payload("In Playlist")}], "next": None},
    }
    with patch("httpx.AsyncClient.request", new=AsyncMock(return_value=_fake_response(playlist))):
        resp = client.get("/integrations/spotify/playlists/pl1")

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "My Mix"
    assert data["tracks_count"] == 2
    assert len(data["tracks"]) == 1
    assert data["tracks"][0]["name"] == "In Playlist"


def test_spotify_data_endpoints_use_stored_token(client, db_session, monkeypatch):
    """No header → the stored (auto-refreshed) token is used; ``?token=`` is ignored."""
    _configure_spotify(monkeypatch)
    _seed_tokens(db_session)

    get_mock = AsyncMock(return_value=_fake_response({"items": []}))
    with patch("httpx.AsyncClient.request", new=get_mock):
        resp = client.get("/integrations/spotify/top-tracks?token=SHOULD-BE-IGNORED")

    assert resp.status_code == 200
    sent_headers = get_mock.await_args.kwargs["headers"]
    assert sent_headers["Authorization"] == "Bearer STORED-ACCESS"


def test_spotify_header_token_override(client, monkeypatch):
    """The legacy ``X-Spotify-Token`` header still wins over stored tokens."""
    _configure_spotify(monkeypatch)

    get_mock = AsyncMock(return_value=_fake_response({"items": [{"track": _track_payload()}]}))
    with patch("httpx.AsyncClient.request", new=get_mock):
        resp = client.get("/integrations/spotify/recently-played", headers=SPOTIFY_TOKEN_HEADER)

    assert resp.status_code == 200
    assert get_mock.await_args.kwargs["headers"]["Authorization"] == "Bearer xyz"
    assert resp.json()[0]["track"]["name"] == "Song"


def test_spotify_data_endpoints_require_connection(client):
    # No header and no stored token → 401 reconnect error (never a token leak).
    for path in ("currently-playing", "recently-played", "top-artists", "top-tracks", "playlists"):
        resp = client.get(f"/integrations/spotify/{path}")
        assert resp.status_code == 401, path
    for method, path in (
        ("put", "play"),
        ("put", "pause"),
        ("post", "next"),
        ("post", "previous"),
    ):
        resp = getattr(client, method)(f"/integrations/spotify/{path}")
        assert resp.status_code == 401, path


def test_spotify_query_token_never_authenticates(client):
    # ?token= must not be accepted — Bearer credentials never travel in URLs
    # (access logs, browser history, Referer). Header is now optional, so the
    # request falls through to the stored-token path → 401 when not connected.
    for path in ("currently-playing", "recently-played", "top-artists", "top-tracks", "playlists"):
        resp = client.get(f"/integrations/spotify/{path}?token=xyz")
        assert resp.status_code == 401, path


# ---------------------------------------------------------------------------
# Playback control
# ---------------------------------------------------------------------------


def test_spotify_play_empty_body(client, db_session, monkeypatch):
    """``PUT /play`` with no body resumes on the active device (empty JSON)."""
    _configure_spotify(monkeypatch)
    _seed_tokens(db_session)

    request_mock = AsyncMock(return_value=_fake_response({}, status_code=204))
    with patch("httpx.AsyncClient.request", new=request_mock):
        resp = client.put("/integrations/spotify/play")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    call = request_mock.await_args
    assert call.args[0] == "PUT"
    assert call.args[1] == f"{SPOTIFY_API_BASE}/me/player/play"
    assert call.kwargs["json"] == {}
    assert call.kwargs["params"] == {}


def test_spotify_play_full_body(client, db_session, monkeypatch):
    _configure_spotify(monkeypatch)
    _seed_tokens(db_session)

    request_mock = AsyncMock(return_value=_fake_response({}, status_code=204))
    body = {
        "device_id": "dev1",
        "context_uri": "spotify:playlist:pl1",
        "offset_position": 3,
        "position_ms": 5000,
    }
    with patch("httpx.AsyncClient.request", new=request_mock):
        resp = client.put("/integrations/spotify/play", json=body)

    assert resp.status_code == 200
    call = request_mock.await_args
    assert call.args[0] == "PUT"
    assert call.kwargs["params"] == {"device_id": "dev1"}
    assert call.kwargs["json"] == {
        "context_uri": "spotify:playlist:pl1",
        "offset": {"position": 3},
        "position_ms": 5000,
    }


def test_spotify_play_uris_and_offset_uri(client, db_session, monkeypatch):
    _configure_spotify(monkeypatch)
    _seed_tokens(db_session)

    request_mock = AsyncMock(return_value=_fake_response({}, status_code=204))
    body = {"uris": ["spotify:track:t1", "spotify:track:t2"], "offset_uri": "spotify:track:t2"}
    with patch("httpx.AsyncClient.request", new=request_mock):
        resp = client.put("/integrations/spotify/play", json=body)

    assert resp.status_code == 200
    assert request_mock.await_args.kwargs["json"] == {
        "uris": ["spotify:track:t1", "spotify:track:t2"],
        "offset": {"uri": "spotify:track:t2"},
    }


def test_spotify_pause_next_previous(client, db_session, monkeypatch):
    _configure_spotify(monkeypatch)
    _seed_tokens(db_session)

    request_mock = AsyncMock(return_value=_fake_response({}, status_code=204))
    with patch("httpx.AsyncClient.request", new=request_mock):
        assert client.put("/integrations/spotify/pause?device_id=dev1").status_code == 200
        call = request_mock.await_args
        assert call.args[0] == "PUT"
        assert call.args[1].endswith("/me/player/pause")
        assert call.kwargs["params"] == {"device_id": "dev1"}

        assert client.post("/integrations/spotify/next").status_code == 200
        call = request_mock.await_args
        assert call.args[0] == "POST"
        assert call.args[1].endswith("/me/player/next")
        assert call.kwargs["params"] == {}

        assert client.post("/integrations/spotify/previous?device_id=dev2").status_code == 200
        call = request_mock.await_args
        assert call.args[0] == "POST"
        assert call.args[1].endswith("/me/player/previous")
        assert call.kwargs["params"] == {"device_id": "dev2"}


# ---------------------------------------------------------------------------
# Upstream error mapping (incl. Premium gating)
# ---------------------------------------------------------------------------


def _failing_api(status_code: int, url: str = f"{SPOTIFY_API_BASE}/me/player"):
    fake = MagicMock()
    fake.raise_for_status.side_effect = _http_status_error(status_code, url)
    return patch("httpx.AsyncClient.request", new=AsyncMock(return_value=fake))


def test_spotify_upstream_401_maps_to_reconnect(client, db_session, monkeypatch):
    _configure_spotify(monkeypatch)
    _seed_tokens(db_session)

    with _failing_api(401):
        resp = client.get("/integrations/spotify/currently-playing")

    assert resp.status_code == 401
    assert "reconecta" in resp.json()["detail"].lower()


def test_spotify_upstream_403_maps_to_premium_error(client, db_session, monkeypatch):
    """Free accounts get 403 from playback control — surface a clear Premium error."""
    _configure_spotify(monkeypatch)
    _seed_tokens(db_session)

    with _failing_api(403, url=f"{SPOTIFY_API_BASE}/me/player/play"):
        resp = client.put("/integrations/spotify/play", json={})

    assert resp.status_code == 403
    assert "premium" in resp.json()["detail"].lower()


def test_spotify_upstream_404_maps(client, db_session, monkeypatch):
    """404 on player endpoints = no active device / nothing found."""
    _configure_spotify(monkeypatch)
    _seed_tokens(db_session)

    with _failing_api(404, url=f"{SPOTIFY_API_BASE}/me/player/next"):
        resp = client.post("/integrations/spotify/next")

    assert resp.status_code == 404
    assert "dispositivo" in resp.json()["detail"].lower()


def test_spotify_upstream_429_maps(client, db_session, monkeypatch):
    _configure_spotify(monkeypatch)
    _seed_tokens(db_session)

    with _failing_api(429):
        resp = client.get("/integrations/spotify/recently-played")

    assert resp.status_code == 429


def test_spotify_upstream_500_maps_to_502(client, db_session, monkeypatch):
    _configure_spotify(monkeypatch)
    _seed_tokens(db_session)

    with _failing_api(500):
        resp = client.get("/integrations/spotify/playlists")

    assert resp.status_code == 502


# ---------------------------------------------------------------------------
# Token refresh (shared integration_token_service + spotify refresher)
# ---------------------------------------------------------------------------


def test_spotify_expired_token_refreshes(client, db_session, monkeypatch):
    """Spotify does NOT rotate refresh tokens — a refresh response without
    ``refresh_token`` must keep the stored one."""
    _configure_spotify(monkeypatch)
    _seed_tokens(db_session, expires_in=-100)  # already expired

    refresh_payload = {
        "access_token": "NEW-ACCESS",
        "expires_in": 3600,
        "token_type": "Bearer",
        # no refresh_token — Spotify keeps the same one
    }
    post_mock = AsyncMock(return_value=_fake_response(refresh_payload))
    request_mock = AsyncMock(return_value=_fake_response({"items": []}))

    with (
        patch("httpx.AsyncClient.post", new=post_mock),
        patch("httpx.AsyncClient.request", new=request_mock),
    ):
        resp = client.get("/integrations/spotify/top-tracks")

    assert resp.status_code == 200
    # Refresh call hit the token endpoint with the OLD refresh token + Basic auth.
    post_call = post_mock.await_args
    assert "accounts.spotify.com/api/token" in post_call.args[0]
    assert post_call.kwargs["data"]["grant_type"] == "refresh_token"
    assert post_call.kwargs["data"]["refresh_token"] == "STORED-REFRESH"
    # The API call used the NEW access token.
    assert request_mock.await_args.kwargs["headers"]["Authorization"] == "Bearer NEW-ACCESS"
    # Stored refresh token kept (no rotation), access token updated.
    row = its.get_stored_token(db_session, its.PROVIDER_SPOTIFY)
    assert row.access_token == "NEW-ACCESS"
    assert its.decrypt_token(row.refresh_token_encrypted) == "STORED-REFRESH"


def test_spotify_refresh_failure_returns_401(client, db_session, monkeypatch):
    _configure_spotify(monkeypatch)
    _seed_tokens(db_session, expires_in=-100)

    fake_response = MagicMock()
    fake_response.raise_for_status.side_effect = _http_status_error(400, "https://accounts.spotify.com/api/token")

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=fake_response)):
        resp = client.get("/integrations/spotify/recently-played")

    assert resp.status_code == 401
    assert "conectar" in resp.json()["detail"].lower()


def test_spotify_valid_token_skips_refresh(client, db_session, monkeypatch):
    _configure_spotify(monkeypatch)
    _seed_tokens(db_session, expires_in=3600)

    post_mock = AsyncMock()
    request_mock = AsyncMock(return_value=_fake_response({"items": []}))
    with (
        patch("httpx.AsyncClient.post", new=post_mock),
        patch("httpx.AsyncClient.request", new=request_mock),
    ):
        resp = client.get("/integrations/spotify/playlists")

    assert resp.status_code == 200
    post_mock.assert_not_awaited()  # no refresh needed
