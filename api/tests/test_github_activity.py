"""GitHub activity for the analytics page (#1499): Events API bucketing,
API-first endpoint and webhook fallback."""

import asyncio
from datetime import date

import httpx
from fastapi.testclient import TestClient
from services import github_activity as gh

TODAY = date(2026, 11, 22)  # a Sunday
CURRENT_MONDAY = "2026-11-16"


def _ev(kind: str, day: str):
    return {"type": kind, "created_at": f"{day}T10:00:00Z"}


def test_bucket_weekly_groups_by_iso_week_and_type():
    events = [
        _ev("PushEvent", "2026-11-22"),
        _ev("PushEvent", "2026-11-16"),
        _ev("PullRequestEvent", "2026-11-17"),
        _ev("IssuesEvent", "2026-11-09"),
        _ev("IssueCommentEvent", "2026-11-10"),
        _ev("PullRequestReviewCommentEvent", "2026-11-10"),
        _ev("WatchEvent", "2026-11-18"),  # ignored type
    ]
    out = gh.bucket_weekly(events, TODAY)
    weekly = {w["week_start"]: w for w in out["weekly"]}
    assert len(out["weekly"]) == gh.WEEKS
    assert out["weekly"][-1]["week_start"] == CURRENT_MONDAY
    assert weekly[CURRENT_MONDAY]["pushes"] == 2
    assert weekly[CURRENT_MONDAY]["pull_requests"] == 1
    assert weekly["2026-11-09"]["issues"] == 1
    assert weekly["2026-11-09"]["comments"] == 2
    assert out["truncated"] is False


def test_bucket_weekly_ignores_events_outside_window_and_bad_dates():
    events = [
        _ev("PushEvent", "2025-01-01"),
        {"type": "PushEvent"},
        {"created_at": "nope"},
    ]
    out = gh.bucket_weekly(events, TODAY)
    assert sum(w["pushes"] for w in out["weekly"]) == 0


def test_bucket_weekly_flags_truncation_at_api_cap():
    events = [_ev("PushEvent", "2026-11-20")] * (gh.PER_PAGE * gh.MAX_PAGES)
    assert gh.bucket_weekly(events, TODAY)["truncated"] is True


def test_fetch_weekly_activity_none_when_not_configured(monkeypatch):
    monkeypatch.setattr(gh.settings, "github_token", "")
    monkeypatch.setattr(gh.settings, "github_username", "")
    assert asyncio.run(gh.fetch_weekly_activity(TODAY)) is None


def test_fetch_weekly_activity_uses_events_and_caches(monkeypatch):
    gh.clear_cache()
    monkeypatch.setattr(gh.settings, "github_token", "")
    monkeypatch.setattr(gh.settings, "github_username", "octo")
    calls = {"n": 0}

    async def fake_events(login):
        calls["n"] += 1
        assert login == "octo"
        return [_ev("PushEvent", "2026-11-20")]

    monkeypatch.setattr(gh, "fetch_user_events", fake_events)
    first = asyncio.run(gh.fetch_weekly_activity(TODAY))
    second = asyncio.run(gh.fetch_weekly_activity(TODAY))
    assert first["available"] is True and first["source"] == "events" and first["login"] == "octo"
    assert first["weekly"][-1]["pushes"] == 1
    assert second is first and calls["n"] == 1
    gh.clear_cache()


def _http_error(status: int, headers: dict | None = None, text: str = ""):
    request = httpx.Request("GET", "https://api.github.com/x")
    response = httpx.Response(status, headers=headers or {}, text=text, request=request)
    return httpx.HTTPStatusError("boom", request=request, response=response)


def test_classify_failure_reasons():
    assert gh.classify_failure(_http_error(403, {"x-ratelimit-remaining": "0"})) == "rate_limited"
    assert gh.classify_failure(_http_error(403, text="API rate limit exceeded")) == "rate_limited"
    assert gh.classify_failure(_http_error(429)) == "rate_limited"
    assert gh.classify_failure(_http_error(401)) == "bad_credentials"
    assert gh.classify_failure(RuntimeError("net")) == "unavailable"


def test_fetch_weekly_activity_reports_error_when_api_fails(monkeypatch):
    gh.clear_cache()
    monkeypatch.setattr(gh.settings, "github_token", "")
    monkeypatch.setattr(gh.settings, "github_username", "octo")

    async def boom(login):
        raise _http_error(403, {"x-ratelimit-remaining": "0"})

    monkeypatch.setattr(gh, "fetch_user_events", boom)
    out = asyncio.run(gh.fetch_weekly_activity(TODAY))
    assert out["available"] is False and out["error"] == "rate_limited"


def test_fetch_weekly_activity_serves_stale_cache_on_failure(monkeypatch):
    gh.clear_cache()
    monkeypatch.setattr(gh.settings, "github_token", "")
    monkeypatch.setattr(gh.settings, "github_username", "octo")

    async def ok(login):
        return [_ev("PushEvent", "2026-11-20")]

    monkeypatch.setattr(gh, "fetch_user_events", ok)
    first = asyncio.run(gh.fetch_weekly_activity(TODAY))
    # Expire the cache entry, then make the API fail.
    key = next(iter(gh._cache))
    gh._cache[key] = (gh._cache[key][0] - gh.CACHE_TTL - 1, first)

    async def boom(login):
        raise _http_error(403, {"x-ratelimit-remaining": "0"})

    monkeypatch.setattr(gh, "fetch_user_events", boom)
    out = asyncio.run(gh.fetch_weekly_activity(TODAY))
    assert out["available"] is True and out["stale"] is True
    assert out["weekly"][-1]["pushes"] == 1
    gh.clear_cache()


def test_week_starts_are_consecutive_mondays():
    mondays = gh.week_starts(TODAY)
    assert len(mondays) == gh.WEEKS
    assert mondays[-1].isoformat() == CURRENT_MONDAY
    assert all((b - a).days == 7 for a, b in zip(mondays, mondays[1:], strict=False))


def test_graphql_query_has_one_alias_per_week_and_clamps_to_now():
    from datetime import UTC, datetime

    now = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
    q = gh.build_graphql_query(gh.week_starts(TODAY), now)
    assert q.count("contributionsCollection") == gh.WEEKS
    assert "w0:" in q and f"w{gh.WEEKS - 1}:" in q
    assert 'to: "2026-11-22T12:00:00Z"' in q  # current week ends now, not Sunday 23:59:59


def test_parse_graphql_weeks_maps_contribution_fields():
    mondays = gh.week_starts(TODAY)
    viewer = {
        "login": "octo",
        f"w{gh.WEEKS - 1}": {
            "totalCommitContributions": 7,
            "totalPullRequestContributions": 2,
            "totalIssueContributions": 3,
            "totalPullRequestReviewContributions": 4,
        },
    }
    weekly = gh.parse_graphql_weeks(viewer, mondays)
    assert weekly[-1] == {
        "week_start": CURRENT_MONDAY,
        "pushes": 7,
        "pull_requests": 2,
        "issues": 3,
        "comments": 4,
    }
    assert weekly[0]["pushes"] == 0


def test_fetch_weekly_activity_prefers_graphql_with_token(monkeypatch):
    gh.clear_cache()
    monkeypatch.setattr(gh.settings, "github_token", "t0ken")
    monkeypatch.setattr(gh.settings, "github_username", "")

    async def fake_graphql(today, now):
        return "octo", gh.parse_graphql_weeks({}, gh.week_starts(today))

    async def no_events(login):
        raise AssertionError("Events API must not be used when GraphQL works")

    monkeypatch.setattr(gh, "fetch_graphql_weekly", fake_graphql)
    monkeypatch.setattr(gh, "fetch_user_events", no_events)
    out = asyncio.run(gh.fetch_weekly_activity(TODAY))
    assert out["source"] == "graphql" and out["login"] == "octo" and out["truncated"] is False
    gh.clear_cache()


def test_fetch_weekly_activity_falls_back_to_events_when_graphql_fails(monkeypatch):
    gh.clear_cache()
    monkeypatch.setattr(gh.settings, "github_token", "t0ken")
    monkeypatch.setattr(gh.settings, "github_username", "octo")

    async def bad_graphql(today, now):
        raise RuntimeError("graphql down")

    async def fake_events(login):
        return [_ev("PushEvent", "2026-11-20")]

    async def fake_login():
        return "octo"

    monkeypatch.setattr(gh, "fetch_graphql_weekly", bad_graphql)
    monkeypatch.setattr(gh, "_resolve_login", fake_login)
    monkeypatch.setattr(gh, "fetch_user_events", fake_events)
    out = asyncio.run(gh.fetch_weekly_activity(TODAY))
    assert out["source"] == "events" and out["weekly"][-1]["pushes"] == 1
    gh.clear_cache()


def test_endpoint_prefers_api_activity(client: TestClient, monkeypatch):
    payload = {
        "available": True,
        "source": "api",
        "login": "octo",
        "weekly": [],
        "truncated": False,
    }

    async def fake():
        return payload

    monkeypatch.setattr("routers.analytics.fetch_weekly_activity", fake)
    assert client.get("/analytics/github").json() == payload


def test_endpoint_falls_back_to_webhook_events(client: TestClient, monkeypatch):
    async def none():
        return None

    monkeypatch.setattr("routers.analytics.fetch_weekly_activity", none)
    data = client.get("/analytics/github").json()
    assert data["source"] == "webhook"
    assert data["available"] is False
    assert data["weekly"] == []


def test_endpoint_reports_error_reason_with_webhook_fallback(client: TestClient, monkeypatch):
    async def failed():
        return {
            "available": False,
            "source": None,
            "weekly": [],
            "error": "rate_limited",
        }

    monkeypatch.setattr("routers.analytics.fetch_weekly_activity", failed)
    data = client.get("/analytics/github").json()
    assert data["error"] == "rate_limited"
    assert data["source"] == "webhook"


def test_contribution_streaks_current_survives_empty_today():
    days = [
        {"date": "2026-11-19", "count": 5},
        {"date": "2026-11-20", "count": 3},
        {"date": "2026-11-21", "count": 2},
        {"date": "2026-11-22", "count": 0},  # today, still in progress
    ]
    out = gh.contribution_streaks(days, TODAY)
    assert out["current"] == 3  # 19+20+21; an empty today does not break it
    assert out["longest"] == 3


def test_contribution_streaks_dead_when_yesterday_empty():
    days = [
        {"date": "2026-11-20", "count": 5},
        {"date": "2026-11-21", "count": 0},
        {"date": "2026-11-22", "count": 0},
    ]
    out = gh.contribution_streaks(days, TODAY)
    assert out["current"] == 0  # yesterday had no contributions: streak already dead
    assert out["longest"] == 1


def test_contribution_streaks_gap_breaks_current():
    days = [
        {"date": "2026-11-21", "count": 1},
        {"date": "2026-11-22", "count": 4},
    ]
    out = gh.contribution_streaks(days, TODAY)
    assert out["current"] == 2


def test_parse_extras_maps_repos_languages_prs_calendar():
    data = {
        "win": {
            "contributionsCollection": {
                "commitContributionsByRepository": [
                    {
                        "repository": {
                            "nameWithOwner": "u/a",
                            "isPrivate": True,
                            "primaryLanguage": {"name": "Python", "color": "#3572A5"},
                        },
                        "contributions": {"totalCount": 8},
                    },
                    {
                        "repository": {
                            "nameWithOwner": "u/b",
                            "isPrivate": False,
                            "primaryLanguage": None,
                        },
                        "contributions": {"totalCount": 2},
                    },
                ],
                "contributionCalendar": {
                    "totalContributions": 42,
                    "weeks": [
                        {
                            "contributionDays": [
                                {"date": "2026-11-21", "contributionCount": 10},
                                {"date": "2026-11-22", "contributionCount": 3},
                            ]
                        }
                    ],
                },
            }
        },
        "disc": {"discussionCount": 2},
        "commented": {"issueCount": 9},
        "closedIssues": {"issueCount": 4},
        "merged": {
            "issueCount": 3,
            "nodes": [
                {
                    "additions": 10,
                    "deletions": 2,
                    "createdAt": "2026-11-20T10:00:00Z",
                    "mergedAt": "2026-11-20T12:00:00Z",
                }
            ],
        },
    }
    out = gh.parse_extras(data, TODAY)
    assert out["repos"][0] == {
        "name": "u/a",
        "private": True,
        "language": "Python",
        "color": "#3572A5",
        "commits": 8,
    }
    assert out["languages"][0]["share"] == 80.0  # Python: 8 of 10
    assert out["languages"][1]["name"] is None
    assert out["prs"]["merged"] == 3
    assert out["prs"]["median_merge_hours"] == 2.0
    assert out["prs"]["additions"] == 10 and out["prs"]["deletions"] == 2
    assert out["prs"]["sampled"] is True
    assert out["threads"] == {"commented": 9, "issues_closed": 4, "discussions": 2}
    assert out["calendar"]["active_days"] == 2
    assert out["calendar"]["current_streak"] == 2  # 21+22 consecutive
    assert out["calendar"]["best_day"]["count"] == 10


def test_fetch_weekly_activity_includes_summary_when_graphql_ok(monkeypatch):
    gh.clear_cache()
    monkeypatch.setattr(gh.settings, "github_token", "t0ken")
    monkeypatch.setattr(gh.settings, "github_username", "")

    async def fake_weekly(today, now):
        return "octo", []

    async def fake_extras(login, today, now):
        return {"marker": login}

    monkeypatch.setattr(gh, "fetch_graphql_weekly", fake_weekly)
    monkeypatch.setattr(gh, "fetch_graphql_extras", fake_extras)
    out = asyncio.run(gh.fetch_weekly_activity(TODAY))
    assert out["summary"] == {"marker": "octo"}
    gh.clear_cache()
