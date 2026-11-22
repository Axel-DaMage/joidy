"""GitHub activity for the analytics page, read from the GitHub Events API (#1499).

Connecting an account (token or username) is enough to chart weekly activity:
``GET /users/{login}/events`` returns the user's recent events (up to 300 over
the last 90 days; private events are included when authenticated as that
user). Webhook-recorded events (``analytics_service``) remain the fallback for
setups without a token/username or when the API call fails.

Results are cached in-process for ``CACHE_TTL`` seconds so opening the page
repeatedly does not burn the GitHub rate limit.
"""

import time
from datetime import UTC, date, datetime, timedelta

import httpx
from config import settings
from services.http_client import http_client

GITHUB_API = "https://api.github.com"
WEEKS = 12
PER_PAGE = 100
MAX_PAGES = 3  # the Events API never returns more than 300 events
CACHE_TTL = 600.0

# GitHub event type → output bucket (same keys as the webhook-based payload).
EVENT_BUCKET = {
    "PushEvent": "pushes",
    "PullRequestEvent": "pull_requests",
    "IssuesEvent": "issues",
    "IssueCommentEvent": "comments",
    "PullRequestReviewCommentEvent": "comments",
}

_cache: dict[str, tuple[float, dict]] = {}


def clear_cache() -> None:
    _cache.clear()


def _headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Joidy-App",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


def is_configured() -> bool:
    return bool(settings.github_token or settings.github_username)


async def _get(url: str, params: dict | None = None):
    async with http_client(timeout=20.0) as client:
        r = await client.get(
            f"{GITHUB_API}{url}", headers=_headers(), params=params or {}
        )
        r.raise_for_status()
        return r.json()


async def _resolve_login() -> str:
    if settings.github_token:
        return (await _get("/user"))["login"]
    return settings.github_username


async def fetch_user_events(login: str) -> list[dict]:
    """Newest-first events for ``login`` (paginated, capped at 300 by GitHub)."""
    events: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        batch = await _get(
            f"/users/{login}/events", {"per_page": PER_PAGE, "page": page}
        )
        events.extend(batch)
        if len(batch) < PER_PAGE:
            break
    return events


def bucket_weekly(events: list[dict], today: date, weeks: int = WEEKS) -> dict:
    """Group events into ISO weeks (Monday start), oldest → newest.

    ``truncated`` is true when the API returned its maximum number of events
    and the oldest one is still inside the window — older weeks may then be
    undercounted.
    """
    current_monday = today - timedelta(days=today.weekday())
    first_monday = current_monday - timedelta(weeks=weeks - 1)
    buckets = {
        (first_monday + timedelta(weeks=i)).isoformat(): {
            "pushes": 0,
            "pull_requests": 0,
            "issues": 0,
            "comments": 0,
        }
        for i in range(weeks)
    }
    oldest: date | None = None
    for ev in events:
        try:
            day = datetime.fromisoformat(ev["created_at"].replace("Z", "+00:00")).date()
        except (KeyError, ValueError, AttributeError):
            continue
        oldest = day if oldest is None or day < oldest else oldest
        key = EVENT_BUCKET.get(ev.get("type", ""))
        week = (day - timedelta(days=day.weekday())).isoformat()
        if key and week in buckets:
            buckets[week][key] += 1
    weekly = [{"week_start": wk, **vals} for wk, vals in buckets.items()]
    truncated = (
        len(events) >= PER_PAGE * MAX_PAGES
        and oldest is not None
        and oldest > first_monday
    )
    return {"weekly": weekly, "truncated": truncated}


def classify_failure(exc: Exception) -> str:
    """Map an API failure to a stable reason code the UI can explain."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        remaining = exc.response.headers.get("x-ratelimit-remaining")
        if status == 429 or (
            status == 403
            and (remaining == "0" or "rate limit" in exc.response.text.lower())
        ):
            return "rate_limited"
        if status in (401, 403):
            return "bad_credentials"
    return "unavailable"


async def fetch_weekly_activity(today: date | None = None) -> dict | None:
    """Weekly activity from the GitHub API.

    Returns ``None`` when no account is configured. On API failure it returns
    the last cached result flagged ``stale`` if there is one, otherwise a
    payload with ``available: False`` and an ``error`` reason — the caller
    then falls back to webhook-recorded events.
    """
    if not is_configured():
        return None
    login_hint = settings.github_username or "token"
    cached = _cache.get(login_hint)
    now = time.monotonic()
    if cached and now - cached[0] < CACHE_TTL:
        return cached[1]
    try:
        login = await _resolve_login()
        events = await fetch_user_events(login)
    except Exception as exc:  # network, auth, rate limit — degrade gracefully
        if cached:
            return {**cached[1], "stale": True}
        return {
            "available": False,
            "source": None,
            "weekly": [],
            "error": classify_failure(exc),
        }
    today = today or datetime.now(UTC).date()
    result = {
        "available": True,
        "source": "api",
        "login": login,
        "stale": False,
        **bucket_weekly(events, today),
    }
    _cache[login_hint] = (now, result)
    return result
