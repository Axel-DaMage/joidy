"""Spotify OAuth and Web API helpers (#45).

Server-side confidential client: the standard Authorization Code flow with
the app's ``client_secret`` (HTTP Basic on the token endpoint). PKCE is
supported by Spotify but exists for *public* clients that cannot keep a
secret — Joidy exchanges the code server-side where the secret never reaches
the browser, so auth-code + the HMAC-signed ``state`` (CSRF, #1328) is the
correct flow. Adding PKCE on top would only complicate the exchange for no
security gain here.

Tokens persist encrypted in ``integration_tokens`` (provider ``"spotify"``)
via ``services.integration_token_service`` — never returned to the browser.
Access tokens expire ~1h and refresh automatically; Spotify does NOT rotate
refresh tokens (a refresh response may omit ``refresh_token`` — the stored
one is kept) and they expire 6 months after the grant. Spotify also exposes
NO token-revocation endpoint (spotify/web-api#600, wontfix): disconnecting
means deleting the stored row — the refresh token dies with it and remaining
access tokens self-expire within the hour. Users can additionally revoke the
app at https://www.spotify.com/account/apps/.

Playback control endpoints (``PUT /play``, ``pause``, ``next``, ``previous``)
require a Spotify **Premium** account: free accounts get ``403`` ("Premium
required") / ``404`` ("No active device found") from Spotify, which the
router maps to clear errors.
"""

import logging
from typing import Any

import httpx
from config import settings
from services.http_client import http_client

logger = logging.getLogger(__name__)

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"  # noqa: S105 — OAuth endpoint URL, not a password
SPOTIFY_API = "https://api.spotify.com/v1"

# Where users can fully revoke app access (Spotify has no revocation API).
SPOTIFY_MANAGE_APPS_URL = "https://www.spotify.com/account/apps/"

# Scopes required by the endpoints below. ``user-read-playback-state`` covers
# GET /me/player*; ``user-modify-playback-state`` covers the control verbs.
# (Spotify deprecated ``user-read-currently-playing`` — playback state scope
# already authorizes the currently-playing read.)
SPOTIFY_SCOPES = (
    "user-read-private user-read-email user-read-playback-state "
    "user-modify-playback-state user-read-recently-played user-top-read "
    "playlist-read-private"
)

# /me/top/* ``time_range`` values accepted by Spotify.
TOP_TIME_RANGES = ("short_term", "medium_term", "long_term")
DEFAULT_TOP_TIME_RANGE = "medium_term"

# Spotify caps list endpoints at 50 items per page.
MAX_PAGE_LIMIT = 50


def get_auth_url(state: str = "") -> str:
    """Build the Spotify OAuth consent URL.

    ``show_dialog=true`` forces the consent screen even when the user
    already authorized the app — same intent as Strava's
    ``approval_prompt=force`` so reconnects always re-confirm scopes.
    """
    if not settings.spotify_client_id or not settings.spotify_redirect_uri:
        raise RuntimeError("Spotify OAuth is not configured")

    params = {
        "client_id": settings.spotify_client_id,
        "redirect_uri": settings.spotify_redirect_uri,
        "response_type": "code",
        "scope": SPOTIFY_SCOPES,
        "show_dialog": "true",
    }
    if state:
        params["state"] = state

    query = httpx.QueryParams(params)
    return f"{SPOTIFY_AUTH_URL}?{query}"


async def exchange_code(code: str) -> dict[str, Any]:
    """Exchange an OAuth authorization code for tokens.

    Spotify accepts client credentials via HTTP Basic; the body carries only
    the grant parameters. Returns the raw token payload — callers persist it
    via ``integration_token_service.store_tokens``.
    """
    if not settings.spotify_client_id or not settings.spotify_client_secret or not settings.spotify_redirect_uri:
        raise RuntimeError("Spotify OAuth is not configured")

    auth = httpx.BasicAuth(settings.spotify_client_id, settings.spotify_client_secret)
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.spotify_redirect_uri,
    }

    async with http_client(timeout=30.0) as client:
        r = await client.post(SPOTIFY_TOKEN_URL, data=payload, auth=auth)
        r.raise_for_status()
        tokens: dict[str, Any] = r.json()
        return tokens


async def refresh_tokens(refresh_token: str) -> dict[str, Any]:
    """Refresh an expired access token.

    Normalized for ``integration_token_service.get_valid_access_token``.
    Spotify does NOT rotate refresh tokens — the response usually omits
    ``refresh_token`` and the stored one must be kept (the service only
    overwrites it when a new value arrives). No ``account_id`` is available
    here; it is populated at connect time / first ``/status`` call instead.
    """
    if not settings.spotify_client_id or not settings.spotify_client_secret:
        raise RuntimeError("Spotify OAuth is not configured")

    auth = httpx.BasicAuth(settings.spotify_client_id, settings.spotify_client_secret)
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }

    async with http_client(timeout=30.0) as client:
        r = await client.post(SPOTIFY_TOKEN_URL, data=payload, auth=auth)
        r.raise_for_status()
        data: dict[str, Any] = r.json()

    return {
        "access_token": data.get("access_token", ""),
        "refresh_token": data.get("refresh_token"),
        "expires_in": data.get("expires_in"),
        "token_type": data.get("token_type", "Bearer"),
        "scope": data.get("scope"),
        "account_id": None,
    }


# ---------------------------------------------------------------------------
# HTTP helpers + normalization
# ---------------------------------------------------------------------------


async def _request(
    token: str,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> httpx.Response:
    """One authenticated call against ``api.spotify.com`` (fixed host — no SSRF)."""
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    async with http_client(timeout=30.0) as client:
        r = await client.request(method, f"{SPOTIFY_API}{path}", headers=headers, params=params or {}, json=json_body)
        r.raise_for_status()
        return r


async def _get_json(token: str, path: str, params: dict[str, Any] | None = None) -> Any:
    r = await _request(token, "GET", path, params=params)
    # Spotify answers 204 No Content for "nothing playing" on player GETs.
    if r.status_code == 204:
        return None
    return r.json()


def _image_url(images: Any) -> str | None:
    """Largest album/artist image — Spotify sorts ``images`` biggest-first."""
    if not isinstance(images, list) or not images:
        return None
    first = images[0]
    if isinstance(first, dict) and first.get("url"):
        return str(first["url"])
    return None


def normalize_artist(artist: dict[str, Any]) -> dict[str, Any]:
    """Spotify artist object → compact frontend shape."""
    return {
        "id": artist.get("id"),
        "uri": artist.get("uri"),
        "name": artist.get("name"),
        "image_url": _image_url(artist.get("images")),
        "genres": artist.get("genres") or [],
        "followers": (artist.get("followers") or {}).get("total"),
        "popularity": artist.get("popularity"),
    }


def normalize_track(track: dict[str, Any] | None) -> dict[str, Any] | None:
    """Spotify track object → flat snake_case shape for the frontend.

    ``album_image_url`` is the largest cover (first entry of Spotify's
    ``images``, which is sorted descending by size).
    """
    if not track:
        return None
    artists = track.get("artists") or []
    album = track.get("album") or {}
    return {
        "id": track.get("id"),
        "uri": track.get("uri"),
        "name": track.get("name"),
        "artists": [
            {"id": a.get("id"), "name": a.get("name"), "uri": a.get("uri")} for a in artists if isinstance(a, dict)
        ],
        "artist_names": ", ".join(a.get("name", "") for a in artists if isinstance(a, dict) and a.get("name")),
        "album": {"id": album.get("id"), "name": album.get("name"), "uri": album.get("uri")},
        "album_name": album.get("name"),
        "album_image_url": _image_url(album.get("images")),
        "duration_ms": track.get("duration_ms"),
        "explicit": track.get("explicit"),
        "preview_url": track.get("preview_url"),
        "is_playable": track.get("is_playable"),
    }


def normalize_playlist(playlist: dict[str, Any]) -> dict[str, Any]:
    """Spotify playlist object → compact shape (owner, counts, cover)."""
    owner = playlist.get("owner") or {}
    images = playlist.get("images") or []
    return {
        "id": playlist.get("id"),
        "uri": playlist.get("uri"),
        "name": playlist.get("name"),
        "description": playlist.get("description"),
        "image_url": _image_url(images),
        "owner": {"id": owner.get("id"), "display_name": owner.get("display_name")},
        "tracks_count": (playlist.get("tracks") or {}).get("total"),
        "public": playlist.get("public"),
        "collaborative": playlist.get("collaborative"),
        "external_url": (playlist.get("external_urls") or {}).get("spotify"),
    }


def normalize_playback_state(state: dict[str, Any] | None) -> dict[str, Any]:
    """Spotify playback-state object → stable frontend shape.

    Always returns the same keys; ``is_playing: false`` with nulls when
    Spotify reports nothing playing (204 upstream).
    """
    if not state:
        return {
            "is_playing": False,
            "progress_ms": 0,
            "duration_ms": None,
            "track": None,
            "context": None,
            "device": None,
            "shuffle_state": False,
            "repeat_state": None,
        }

    item = state.get("item")
    device = state.get("device") or {}
    context = state.get("context") or {}
    ctx_meta = context.get("metadata") or {}
    return {
        "is_playing": bool(state.get("is_playing")),
        "progress_ms": state.get("progress_ms") or 0,
        "duration_ms": (item or {}).get("duration_ms") if isinstance(item, dict) else None,
        "track": normalize_track(item if isinstance(item, dict) else None),
        "context": {
            "type": context.get("type"),
            "uri": context.get("uri"),
            "name": ctx_meta.get("name") or ctx_meta.get("album_name"),
        }
        if context
        else None,
        "device": {
            "id": device.get("id"),
            "name": device.get("name"),
            "type": device.get("type"),
            "is_active": device.get("is_active"),
            "volume_percent": device.get("volume_percent"),
        }
        if device
        else None,
        "shuffle_state": bool(state.get("shuffle_state")),
        "repeat_state": state.get("repeat_state"),
    }


# ---------------------------------------------------------------------------
# Endpoint wrappers
# ---------------------------------------------------------------------------


async def get_profile(token: str) -> dict[str, Any]:
    """``GET /me`` — Spotify user profile (id, display_name, email)."""
    profile: dict[str, Any] = await _get_json(token, "/me")
    return profile


async def get_playback_state(token: str) -> dict[str, Any]:
    """``GET /me/player`` — full playback state incl. device + repeat/shuffle."""
    state: dict[str, Any] | None = await _get_json(token, "/me/player")
    return normalize_playback_state(state)


async def get_recently_played(token: str, limit: int = 20) -> list[dict[str, Any]]:
    """``GET /me/player/recently-played`` → ``[{played_at, track}]``."""
    data = await _get_json(token, "/me/player/recently-played", params={"limit": min(limit, MAX_PAGE_LIMIT)})
    items = (data or {}).get("items", [])
    return [
        {
            "played_at": entry.get("played_at"),
            "track": normalize_track(entry.get("track")),
        }
        for entry in items
        if isinstance(entry, dict)
    ]


def _top_params(time_range: str, limit: int) -> dict[str, Any]:
    return {
        "time_range": time_range if time_range in TOP_TIME_RANGES else DEFAULT_TOP_TIME_RANGE,
        "limit": min(limit, MAX_PAGE_LIMIT),
    }


async def get_top_artists(
    token: str, time_range: str = DEFAULT_TOP_TIME_RANGE, limit: int = 20
) -> list[dict[str, Any]]:
    """``GET /me/top/artists`` → normalized artist list."""
    data = await _get_json(token, "/me/top/artists", params=_top_params(time_range, limit))
    items = (data or {}).get("items", [])
    return [normalize_artist(a) for a in items if isinstance(a, dict)]


async def get_top_tracks(token: str, time_range: str = DEFAULT_TOP_TIME_RANGE, limit: int = 20) -> list[dict[str, Any]]:
    """``GET /me/top/tracks`` → normalized track list."""
    data = await _get_json(token, "/me/top/tracks", params=_top_params(time_range, limit))
    items = (data or {}).get("items", [])
    return [t for t in (normalize_track(item) for item in items if isinstance(item, dict)) if t is not None]


async def get_playlists(token: str, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
    """``GET /me/playlists`` → normalized playlist list."""
    data = await _get_json(
        token,
        "/me/playlists",
        params={"limit": min(limit, MAX_PAGE_LIMIT), "offset": max(offset, 0)},
    )
    items = (data or {}).get("items", [])
    return [normalize_playlist(p) for p in items if isinstance(p, dict)]


async def get_playlist(token: str, playlist_id: str) -> dict[str, Any]:
    """``GET /playlists/{id}`` → playlist detail + first page of tracks."""
    data = await _get_json(token, f"/playlists/{playlist_id}")
    if not isinstance(data, dict):
        raise RuntimeError("Unexpected Spotify playlist payload")
    playlist = normalize_playlist(data)
    raw_tracks = ((data.get("tracks") or {}).get("items")) or []
    playlist["tracks"] = [
        t
        for t in (normalize_track((item or {}).get("track") if isinstance(item, dict) else None) for item in raw_tracks)
        if t is not None
    ]
    return playlist


# ---------------------------------------------------------------------------
# Playback control (Premium required — see module docstring)
# ---------------------------------------------------------------------------


async def play(
    token: str,
    *,
    device_id: str | None = None,
    context_uri: str | None = None,
    uris: list[str] | None = None,
    offset_position: int | None = None,
    offset_uri: str | None = None,
    position_ms: int | None = None,
) -> None:
    """``PUT /me/player/play`` — resume playback, optionally on ``device_id``.

    Body mirrors Spotify's: ``context_uri`` (album/playlist/artist context)
    or ``uris`` (explicit track list), ``offset`` as ``{position|uri}``, and
    ``position_ms``. ``device_id`` travels as a query param.
    """
    params: dict[str, Any] = {}
    if device_id:
        params["device_id"] = device_id

    body: dict[str, Any] = {}
    if context_uri:
        body["context_uri"] = context_uri
    if uris:
        body["uris"] = uris
    if offset_position is not None:
        body["offset"] = {"position": offset_position}
    elif offset_uri:
        body["offset"] = {"uri": offset_uri}
    if position_ms is not None:
        body["position_ms"] = position_ms

    # Spotify answers 204; _request already raised on errors.
    await _request(token, "PUT", "/me/player/play", params=params, json_body=body or {})


async def pause(token: str, device_id: str | None = None) -> None:
    """``PUT /me/player/pause``."""
    params = {"device_id": device_id} if device_id else {}
    await _request(token, "PUT", "/me/player/pause", params=params)


async def next_track(token: str, device_id: str | None = None) -> None:
    """``POST /me/player/next``."""
    params = {"device_id": device_id} if device_id else {}
    await _request(token, "POST", "/me/player/next", params=params)


async def previous_track(token: str, device_id: str | None = None) -> None:
    """``POST /me/player/previous``."""
    params = {"device_id": device_id} if device_id else {}
    await _request(token, "POST", "/me/player/previous", params=params)
