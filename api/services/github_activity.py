"""GitHub activity for the analytics page, read from the GitHub API (#1499).

Connecting an account is enough to chart weekly activity — no webhooks:

1. **Token → GraphQL** (``source: "graphql"``): one request with a
   ``contributionsCollection`` per ISO week gives commits, PRs opened, issues
   opened and PR reviews for the full 12 weeks, however active the account is.
2. **Username only → Events API** (``source: "events"``): ``/users/{login}/events``
   returns at most 300 recent events, so very active accounts are truncated
   (flagged via ``truncated``).
   With a token a second, soft-failing request adds a ``summary`` (repos,
   languages, PR stats, contribution calendar); the weekly chart never depends
   on it.
3. Webhook-recorded events (``analytics_service``) remain the last fallback.

Results are cached in-process for ``CACHE_TTL`` seconds so opening the page
repeatedly does not burn the GitHub rate limit.
"""

import statistics
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

_CONTRIB_FIELDS = (
    "totalCommitContributions totalPullRequestContributions "
    "totalIssueContributions totalPullRequestReviewContributions"
)
# GraphQL contribution field → output bucket (reviews fill the "comments" bucket).
_GRAPHQL_BUCKET = {
    "totalCommitContributions": "pushes",
    "totalPullRequestContributions": "pull_requests",
    "totalIssueContributions": "issues",
    "totalPullRequestReviewContributions": "comments",
}


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


def week_starts(today: date, weeks: int = WEEKS) -> list[date]:
    """Mondays of the last ``weeks`` ISO weeks, oldest → newest."""
    current = today - timedelta(days=today.weekday())
    return [current - timedelta(weeks=weeks - 1 - i) for i in range(weeks)]


TOP_REPOS = 8
TOP_LANGUAGES = 6
MERGED_PR_SAMPLE = 100  # GraphQL search page size limit


def build_extras_query(login: str, start: datetime, now: datetime) -> str:
    """Repos/languages by commits, PR stats and contribution calendar for the window."""
    since = f"{start:%Y-%m-%d}"
    return f"""query {{
  win: viewer {{ contributionsCollection(from: "{start:%Y-%m-%dT%H:%M:%SZ}", to: "{now:%Y-%m-%dT%H:%M:%SZ}") {{
    commitContributionsByRepository(maxRepositories: 25) {{
      repository {{ nameWithOwner isPrivate primaryLanguage {{ name color }} }}
      contributions {{ totalCount }}
    }}
    contributionCalendar {{ totalContributions weeks {{ contributionDays {{ date contributionCount }} }} }}
  }} }}
  disc: search(query: "author:{login} created:>={since}", type: DISCUSSION, first: 1) {{ discussionCount }}
  commented: search(query: "commenter:{login} updated:>={since}", type: ISSUE, first: 1) {{ issueCount }}
  closedIssues: search(query: "author:{login} is:issue is:closed closed:>={since}", type: ISSUE, first: 1) {{ issueCount }}
  merged: search(query: "author:{login} is:pr is:merged merged:>={since}", type: ISSUE, first: {MERGED_PR_SAMPLE}) {{
    issueCount
    nodes {{ ... on PullRequest {{ additions deletions createdAt mergedAt }} }}
  }}
}}"""


def contribution_streaks(days: list[dict], today: date) -> dict:
    """Current/longest run of days with contributions (ascending ``days``).

    The current streak survives an empty *today* (the day is not over yet).
    """
    longest = run = 0
    for d in days:
        run = run + 1 if d["count"] > 0 else 0
        longest = max(longest, run)
    by_date = {d["date"]: d["count"] for d in days}
    cursor = (
        today if by_date.get(today.isoformat(), 0) > 0 else today - timedelta(days=1)
    )
    current = 0
    while by_date.get(cursor.isoformat(), 0) > 0:
        current += 1
        cursor -= timedelta(days=1)
    return {"current": current, "longest": longest}


def _parse_ts(value: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None
    except ValueError:
        return None


def parse_extras(data: dict, today: date) -> dict:
    collection = data["win"]["contributionsCollection"]

    repos = []
    by_language: dict[tuple[str, str | None], int] = {}
    for item in collection["commitContributionsByRepository"]:
        repo = item["repository"]
        commits = int(item["contributions"]["totalCount"])
        lang = repo.get("primaryLanguage") or {}
        repos.append(
            {
                "name": repo["nameWithOwner"],
                "private": bool(repo.get("isPrivate")),
                "language": lang.get("name"),
                "color": lang.get("color"),
                "commits": commits,
            }
        )
        key = (lang.get("name") or "", lang.get("color"))
        by_language[key] = by_language.get(key, 0) + commits
    repos.sort(key=lambda r: r["commits"], reverse=True)

    total_commits = sum(by_language.values()) or 1
    languages = [
        {
            "name": name or None,
            "color": color,
            "commits": commits,
            "share": round(commits / total_commits * 100, 1),
        }
        for (name, color), commits in sorted(
            by_language.items(), key=lambda kv: kv[1], reverse=True
        )
    ][:TOP_LANGUAGES]

    merged = data["merged"]
    hours: list[float] = []
    additions = deletions = 0
    for node in merged.get("nodes") or []:
        if not node:
            continue
        additions += int(node.get("additions") or 0)
        deletions += int(node.get("deletions") or 0)
        created, done = (
            _parse_ts(node.get("createdAt")),
            _parse_ts(node.get("mergedAt")),
        )
        if created and done and done >= created:
            hours.append((done - created).total_seconds() / 3600)

    days = [
        {"date": d["date"], "count": int(d["contributionCount"])}
        for week in collection["contributionCalendar"]["weeks"]
        for d in week["contributionDays"]
    ]
    best = max(days, key=lambda d: d["count"], default=None)
    return {
        "repos": repos[:TOP_REPOS],
        "languages": languages,
        "prs": {
            "merged": int(merged.get("issueCount") or 0),
            "median_merge_hours": round(statistics.median(hours), 2) if hours else None,
            "additions": additions,
            "deletions": deletions,
            "sampled": int(merged.get("issueCount") or 0)
            > len(merged.get("nodes") or []),
        },
        "threads": {
            "commented": int(data["commented"]["issueCount"]),
            "issues_closed": int(data["closedIssues"]["issueCount"]),
            "discussions": int(data["disc"]["discussionCount"]),
        },
        "calendar": {
            "total": int(collection["contributionCalendar"]["totalContributions"]),
            "active_days": sum(1 for d in days if d["count"] > 0),
            "best_day": best if best and best["count"] > 0 else None,
            **{f"{k}_streak": v for k, v in contribution_streaks(days, today).items()},
        },
    }


async def fetch_graphql_extras(login: str, today: date, now: datetime) -> dict | None:
    """Summary block, or ``None`` on any failure (it is strictly optional)."""
    start = datetime.combine(week_starts(today)[0], datetime.min.time(), tzinfo=UTC)
    try:
        async with http_client(timeout=30.0) as client:
            r = await client.post(
                f"{GITHUB_API}/graphql",
                headers=_headers(),
                json={"query": build_extras_query(login, start, now)},
            )
            r.raise_for_status()
            body = r.json()
        if body.get("errors") or not body.get("data"):
            return None
        return parse_extras(body["data"], today)
    except Exception:
        return None


def build_graphql_query(mondays: list[date], now: datetime) -> str:
    """One aliased ``contributionsCollection`` per week (single round trip)."""
    parts = []
    for i, monday in enumerate(mondays):
        start = datetime.combine(monday, datetime.min.time(), tzinfo=UTC)
        end = min(start + timedelta(weeks=1) - timedelta(seconds=1), now)
        parts.append(
            f'w{i}: contributionsCollection(from: "{start:%Y-%m-%dT%H:%M:%SZ}", '
            f'to: "{end:%Y-%m-%dT%H:%M:%SZ}") {{ {_CONTRIB_FIELDS} }}'
        )
    return "query { viewer { login " + " ".join(parts) + " } }"


def parse_graphql_weeks(viewer: dict, mondays: list[date]) -> list[dict]:
    weekly = []
    for i, monday in enumerate(mondays):
        block = viewer.get(f"w{i}") or {}
        row = {
            "week_start": monday.isoformat(),
            "pushes": 0,
            "pull_requests": 0,
            "issues": 0,
            "comments": 0,
        }
        for field, bucket in _GRAPHQL_BUCKET.items():
            row[bucket] = int(block.get(field) or 0)
        weekly.append(row)
    return weekly


async def fetch_graphql_weekly(today: date, now: datetime) -> tuple[str, list[dict]]:
    mondays = week_starts(today)
    async with http_client(timeout=30.0) as client:
        r = await client.post(
            f"{GITHUB_API}/graphql",
            headers=_headers(),
            json={"query": build_graphql_query(mondays, now)},
        )
        r.raise_for_status()
        body = r.json()
    if body.get("errors") or not body.get("data", {}).get("viewer"):
        raise RuntimeError(f"GraphQL error: {str(body.get('errors'))[:200]}")
    viewer = body["data"]["viewer"]
    return viewer["login"], parse_graphql_weeks(viewer, mondays)


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
    now_dt = datetime.now(UTC)
    today = today or now_dt.date()
    result: dict | None = None
    failure: Exception | None = None
    if settings.github_token:
        try:
            login, weekly = await fetch_graphql_weekly(today, now_dt)
            result = {
                "available": True,
                "source": "graphql",
                "login": login,
                "stale": False,
                "truncated": False,
                "weekly": weekly,
                "summary": await fetch_graphql_extras(login, today, now_dt),
            }
        except Exception as exc:  # fall through to the Events API
            failure = exc
    if result is None:
        try:
            login = await _resolve_login()
            events = await fetch_user_events(login)
            result = {
                "available": True,
                "source": "events",
                "login": login,
                "stale": False,
                **bucket_weekly(events, today),
            }
        except Exception as exc:  # network, auth, rate limit — degrade gracefully
            failure = failure or exc
            if cached:
                return {**cached[1], "stale": True}
            return {
                "available": False,
                "source": None,
                "weekly": [],
                "error": classify_failure(exc),
            }
    _cache[login_hint] = (now, result)
    return result
