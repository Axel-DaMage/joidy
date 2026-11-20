"""Strava OAuth and API helpers."""

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from config import settings
from repositories import XPEventRepository
from services.gamification_engine import GamificationResult, process_event
from services.http_client import http_client
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"  # noqa: S105 — OAuth endpoint URL, not a password
STRAVA_DEAUTHORIZE_URL = "https://www.strava.com/oauth/deauthorize"  # noqa: S105 — OAuth endpoint URL, not a password
STRAVA_API = "https://www.strava.com/api/v3"

# Gamification (#44): +5 XP per synced activity, dedup-keyed on the Strava
# activity id so re-syncs/replays can never farm XP (#1320/#1379). The
# amounts live in gamification_engine.DEFAULT_XP_TABLE and stay tunable via
# the xp_* system config keys like every other event.
XP_EVENT_STRAVA_ACTIVITY = "strava_activity"
XP_EVENT_STRAVA_WEEKLY = "strava_weekly_bonus"
STRAVA_ACTIVITY_DEDUP_PREFIX = "strava:activity:"
STRAVA_WEEK_DEDUP_PREFIX = "strava:week:"

# Bounds for POST /sync: Strava returns activities newest-first, so a few
# pages of 100 cover any realistic gap between syncs (webhook covers live
# creates). The early-stop on an all-known page keeps steady-state syncs to
# a single request.
SYNC_PER_PAGE = 100
SYNC_MAX_PAGES = 5


def get_auth_url(state: str = "") -> str:
    """Build the Strava OAuth consent URL."""
    if not settings.strava_client_id or not settings.strava_redirect_uri:
        raise RuntimeError("Strava OAuth is not configured")

    params = {
        "client_id": settings.strava_client_id,
        "redirect_uri": settings.strava_redirect_uri,
        "response_type": "code",
        "approval_prompt": "force",
        "scope": "read,activity:read",
    }
    if state:
        params["state"] = state

    query = httpx.QueryParams(params)
    return f"{STRAVA_AUTH_URL}?{query}"


async def exchange_code(code: str) -> dict[str, Any]:
    """Exchange an OAuth authorization code for tokens."""
    if not settings.strava_client_secret or not settings.strava_redirect_uri:
        raise RuntimeError("Strava OAuth is not configured")

    payload = {
        "client_id": settings.strava_client_id,
        "client_secret": settings.strava_client_secret,
        "code": code,
        "grant_type": "authorization_code",
    }

    async with http_client(timeout=30.0) as client:
        r = await client.post(STRAVA_TOKEN_URL, data=payload)
        r.raise_for_status()
        tokens: dict[str, Any] = r.json()
        return tokens


async def refresh_tokens(refresh_token: str) -> dict[str, Any]:
    """Refresh an expired access token.

    Strava ROTATES refresh tokens: every refresh response carries a new
    ``refresh_token`` and invalidates the previous one, so callers must
    persist the returned value. The response is normalized for
    ``integration_token_service.get_valid_access_token`` (``account_id``
    carries the athlete id from the embedded ``athlete`` object).
    """
    if not settings.strava_client_id or not settings.strava_client_secret:
        raise RuntimeError("Strava OAuth is not configured")

    payload = {
        "client_id": settings.strava_client_id,
        "client_secret": settings.strava_client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }

    async with http_client(timeout=30.0) as client:
        r = await client.post(STRAVA_TOKEN_URL, data=payload)
        r.raise_for_status()
        data: dict[str, Any] = r.json()

    athlete = data.get("athlete") or {}
    return {
        "access_token": data.get("access_token", ""),
        "refresh_token": data.get("refresh_token"),
        "expires_in": data.get("expires_in"),
        "expires_at": _parse_expires_at(data.get("expires_at")),
        "token_type": data.get("token_type", "Bearer"),
        "account_id": str(athlete.get("id")) if athlete.get("id") is not None else None,
    }


def expires_at_from(payload: dict[str, Any]) -> datetime | None:
    """Normalize a Strava token payload's ``expires_at`` (unix timestamp)."""
    return _parse_expires_at(payload.get("expires_at"))


def _parse_expires_at(value: Any) -> datetime | None:
    """Strava returns ``expires_at`` as a unix timestamp; tolerate ISO strings too."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


async def deauthorize(access_token: str) -> None:
    """Revoke the Strava access token (best-effort disconnect)."""
    async with http_client(timeout=30.0) as client:
        r = await client.post(STRAVA_DEAUTHORIZE_URL, data={"access_token": access_token})
        r.raise_for_status()


async def _request(token: str, url: str, params: dict | None = None) -> Any:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    async with http_client(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params=params or {})
        r.raise_for_status()
        return r.json()


async def list_activities(
    token: str,
    per_page: int = 30,
    page: int = 1,
    before: int | None = None,
    after: int | None = None,
) -> list[dict[str, Any]]:
    """List the athlete's activities (paginated, newest first).

    Strava has no server-side ``sport_type`` filter — callers filter the
    returned page with :func:`matches_sport_type`.
    """
    params: dict[str, Any] = {"per_page": min(per_page, 200), "page": page}
    if before is not None:
        params["before"] = before
    if after is not None:
        params["after"] = after

    activities: list[dict[str, Any]] = await _request(token, f"{STRAVA_API}/athlete/activities", params=params)
    return activities


def matches_sport_type(activity: dict[str, Any], sport_type: str) -> bool:
    """Case-insensitive substring match against ``sport_type``/``type``.

    Strava sport types are granular (``TrailRun``, ``VirtualRide``,
    ``MountainBikeRide`` …); substring matching lets ``run``/``ride``/
    ``swim`` style filters hit the whole family without an alias table.
    """
    needle = sport_type.strip().lower()
    if not needle:
        return True
    for key in ("sport_type", "type"):
        value = activity.get(key)
        if isinstance(value, str) and needle in value.lower():
            return True
    return False


async def get_activity(token: str, activity_id: int) -> dict[str, Any]:
    """Get a single activity's full detail (map, laps/splits, elevation, …)."""
    activity: dict[str, Any] = await _request(token, f"{STRAVA_API}/activities/{activity_id}")
    return activity


# Streams the frontend needs for the detail view (map + elevation chart).
DEFAULT_STREAM_KEYS = "time,latlng,altitude,heartrate,watts,cadence,watts_calc,temp"


async def get_activity_streams(token: str, activity_id: int, keys: str = DEFAULT_STREAM_KEYS) -> Any:
    """Get time-series streams for an activity (``key_by_type=true``)."""
    return await _request(
        token,
        f"{STRAVA_API}/activities/{activity_id}/streams",
        params={"keys": keys, "key_by_type": "true"},
    )


async def get_athlete(token: str) -> dict[str, Any]:
    """Get the authenticated athlete's profile."""
    athlete: dict[str, Any] = await _request(token, f"{STRAVA_API}/athlete")
    return athlete


async def get_stats(token: str, athlete_id: str | None = None) -> dict[str, Any]:
    """Get the athlete's stats (recent / year-to-date / all-time)."""
    if athlete_id is None:
        athlete = await get_athlete(token)
        athlete_id = str(athlete.get("id", ""))
    stats: dict[str, Any] = await _request(token, f"{STRAVA_API}/athletes/{athlete_id}/stats")
    return stats


async def list_routes(token: str, per_page: int = 30, page: int = 1) -> list[dict[str, Any]]:
    """List the athlete's saved routes."""
    routes: list[dict[str, Any]] = await _request(
        token,
        f"{STRAVA_API}/athlete/routes",
        params={"per_page": min(per_page, 200), "page": page},
    )
    return routes


# ---------------------------------------------------------------------------
# Sync + gamification (#44)
# ---------------------------------------------------------------------------


def activity_dedup_key(activity_id: Any) -> str:
    return f"{STRAVA_ACTIVITY_DEDUP_PREFIX}{activity_id}"


def activity_iso_week(activity: dict[str, Any]) -> str | None:
    """ISO-8601 week key (``2026-W06``) of the activity's ``start_date``."""
    start = activity.get("start_date")
    if not isinstance(start, str) or not start:
        return None
    try:
        dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
    except ValueError:
        return None
    iso = dt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def activity_already_awarded(db: Session, activity_id: Any) -> bool:
    event = XPEventRepository(db).find_by_dedup_key(XP_EVENT_STRAVA_ACTIVITY, activity_dedup_key(activity_id))
    return event is not None


def award_activity_xp(db: Session, activity: dict[str, Any]) -> GamificationResult | None:
    """Award +5 XP for a Strava activity — idempotent via dedup key.

    Re-syncs, webhook replays and manual re-fetches hit the same
    ``(event_type, dedup_key)`` row and return a zero-award result instead of
    farming XP (#1320/#1379).
    """
    activity_id = activity.get("id")
    if activity_id is None:
        return None

    name = activity.get("name")
    metadata = {
        "strava_activity_id": activity_id,
        "name": name[:180] if isinstance(name, str) else "",
        "sport_type": activity.get("sport_type") or activity.get("type") or "",
        "distance": activity.get("distance"),
        "moving_time": activity.get("moving_time"),
    }
    return process_event(
        db,
        XP_EVENT_STRAVA_ACTIVITY,
        metadata=metadata,
        dedup_key=activity_dedup_key(activity_id),
    )


def award_weekly_bonus(db: Session, week_key: str) -> GamificationResult:
    """Award the once-per-ISO-week Strava bonus (idempotent per week)."""
    return process_event(
        db,
        XP_EVENT_STRAVA_WEEKLY,
        metadata={"strava_week": week_key},
        dedup_key=f"{STRAVA_WEEK_DEDUP_PREFIX}{week_key}",
    )


async def sync_recent_activities(db: Session, token: str, max_pages: int = SYNC_MAX_PAGES) -> dict[str, Any]:
    """Pull recent activities and award XP idempotently.

    Returns ``{"fetched": n, "new": n, "xp_awarded": n, "weeks": [...],
    "bonus_weeks": [...]}``. The weekly bonus is attempted for every ISO
    week present in the fetched window — the dedup key makes repeats no-ops,
    so a missed bonus self-heals on the next sync.
    """
    fetched: list[dict[str, Any]] = []
    new_count = 0
    xp_awarded = 0
    weeks: set[str] = set()

    for page in range(1, max_pages + 1):
        batch = await list_activities(token, per_page=SYNC_PER_PAGE, page=page)
        if not batch:
            break
        fetched.extend(batch)

        page_all_known = True
        for activity in batch:
            activity_id = activity.get("id")
            if activity_id is None:
                continue
            week = activity_iso_week(activity)
            if week:
                weeks.add(week)

            if activity_already_awarded(db, activity_id):
                continue
            page_all_known = False
            result = award_activity_xp(db, activity)
            if result is not None:
                new_count += 1
                xp_awarded += result.xp_awarded

        if page_all_known:
            break

    bonus_weeks: list[str] = []
    for week in sorted(weeks):
        result = award_weekly_bonus(db, week)
        if result.xp_awarded > 0:
            bonus_weeks.append(week)
            xp_awarded += result.xp_awarded

    return {
        "fetched": len(fetched),
        "new": new_count,
        "xp_awarded": xp_awarded,
        "weeks": sorted(weeks),
        "bonus_weeks": bonus_weeks,
    }


def award_single_activity(db: Session, activity: dict[str, Any]) -> dict[str, Any]:
    """Award XP for one webhook-delivered activity (idempotent)."""
    result = award_activity_xp(db, activity)
    week = activity_iso_week(activity)
    bonus_xp = 0
    bonus_awarded = False
    if week:
        bonus = award_weekly_bonus(db, week)
        bonus_awarded = bonus.xp_awarded > 0
        bonus_xp = bonus.xp_awarded
    return {
        "awarded": bool(result and result.xp_awarded > 0),
        "xp_awarded": (result.xp_awarded if result else 0) + bonus_xp,
        "week": week,
        "weekly_bonus": bonus_awarded,
    }


def webhook_owner_matches(stored_account_id: str | None, event_owner_id: Any) -> bool:
    """True when the webhook event's ``owner_id`` matches the connected
    athlete — forged events for other athletes' activities are ignored."""
    if stored_account_id is None:
        # Nothing stored to compare against: accept (single-user app, the
        # event still has to reference a real activity id to award XP).
        return True
    return str(event_owner_id) == str(stored_account_id)
