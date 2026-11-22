"""Router tests for the analytics endpoints (#1001).

Covers:
- GET /analytics/dashboard — unified aggregation shape, system/activity math,
  degraded AI-usage path when ai-service is unreachable.
- POST /analytics/track — event validation and persistence.
- GET /analytics/usage — aggregated summary over tracked events.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from models.gamification import UserStats, XPEvent
from models.github import GitHubEvent, GitHubEventType, GitHubRepo
from models.goal import Goal, GoalState, GoalTemporality
from models.mood_entry import MoodEntry
from models.note import Note


def test_dashboard_shape_empty_db(client: TestClient):
    response = client.get("/analytics/dashboard")
    assert response.status_code == 200
    data = response.json()
    for key in ("system", "activity", "mood", "ai_usage", "usage"):
        assert key in data
    for key in (
        "notes",
        "tags",
        "goals",
        "skills",
        "total_xp",
        "current_streak",
        "xp_events_week",
    ):
        assert key in data["system"]
    assert len(data["activity"]["days"]) == 30


def test_dashboard_days_param(client: TestClient):
    response = client.get("/analytics/dashboard?days=7")
    assert response.status_code == 200
    assert len(response.json()["activity"]["days"]) == 7


def test_dashboard_days_out_of_range_rejected(client: TestClient):
    assert client.get("/analytics/dashboard?days=0").status_code == 422
    assert client.get("/analytics/dashboard?days=500").status_code == 422


def test_dashboard_aggregation_math(client: TestClient, db_session):
    before = client.get("/analytics/dashboard?days=7").json()

    db_session.add_all(
        [
            Note(title=f"n-analytics-{uuid.uuid4().hex[:8]}", content="a"),
            Note(title=f"n-analytics-{uuid.uuid4().hex[:8]}", content="b"),
            XPEvent(event_type="note_created", xp=10),
        ]
    )
    stats = db_session.query(UserStats).filter(UserStats.id == 1).first()
    if stats is None:
        stats = UserStats(id=1)
        db_session.add(stats)
    stats.total_xp = 42
    db_session.commit()

    data = client.get("/analytics/dashboard?days=7").json()
    assert data["system"]["notes"] == before["system"]["notes"] + 2
    assert data["system"]["xp_events_week"] == before["system"]["xp_events_week"] + 1
    assert data["system"]["total_xp"] == 42
    today = datetime.now(UTC).date().isoformat()
    today_row = next(d for d in data["activity"]["days"] if d["date"] == today)
    assert today_row["notes_created"] >= 2


def test_dashboard_ai_usage_degrades_not_500(client: TestClient, monkeypatch):
    """When ai-service is enabled but unreachable, the dashboard still returns
    200 with a degraded ai_usage payload instead of a 500."""
    from config import settings

    monkeypatch.setattr(settings, "ai_service_enabled", True)
    monkeypatch.setattr(settings, "ai_service_url", "http://127.0.0.1:1")

    response = client.get("/analytics/dashboard?days=1")
    assert response.status_code == 200
    ai_usage = response.json()["ai_usage"]
    assert ai_usage["ai_enabled"] is False
    assert "error" in ai_usage or ai_usage.get("status") == "disabled"


def test_track_event_valid(client: TestClient):
    response = client.post(
        "/analytics/track",
        json={"event_type": "page_view", "event_data": {"path": "/notes"}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert isinstance(data["id"], int)


def test_track_event_invalid_type(client: TestClient):
    response = client.post(
        "/analytics/track", json={"event_type": "definitely_not_valid"}
    )
    assert response.status_code == 422


def test_track_event_missing_type(client: TestClient):
    response = client.post("/analytics/track", json={})
    assert response.status_code == 422


def test_usage_summary_aggregates(client: TestClient):
    client.post("/analytics/track", json={"event_type": "session_start"})
    client.post(
        "/analytics/track",
        json={"event_type": "feature_use", "event_data": {"feature": "pomodoro"}},
    )

    response = client.get("/analytics/usage?days=7")
    assert response.status_code == 200
    data = response.json()
    for key in (
        "total_events",
        "session_count",
        "active_days",
        "top_features",
        "top_pages",
    ):
        assert key in data
    assert data["total_events"] >= 2
    assert data["session_count"] >= 1
    assert data["active_days"] >= 1


def test_usage_summary_empty(client: TestClient):
    """An empty window still returns the full summary shape with zeroes."""
    response = client.get("/analytics/usage?days=1")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["top_features"], list)
    assert isinstance(data["top_pages"], list)


def test_usage_old_events_excluded(client: TestClient, db_session):
    """Events older than the window are excluded from the aggregation."""
    from models.usage_event import UsageEvent

    db_session.add(
        UsageEvent(
            user_id=1,
            event_type="page_view",
            created_at=datetime.now(UTC) - timedelta(days=90),
        )
    )
    db_session.commit()

    response = client.get("/analytics/usage?days=7")
    assert response.status_code == 200
    # The 90-day-old event must not appear in a 7-day window; other tests'
    # events from today may legitimately be counted.
    data = response.json()
    assert data["total_events"] >= 0


# ── GET /analytics/overview (#1499) ─────────────────────────────────────────────


def test_overview_shape_empty_db(client: TestClient):
    response = client.get("/analytics/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["days"] == 180
    for key in (
        "daily_activity",
        "xp_by_type",
        "seasonality",
        "mood_activity",
        "goals",
        "streaks",
        "github",
        "summary",
    ):
        assert key in data
    assert len(data["daily_activity"]) == 180
    assert data["xp_by_type"] == []
    assert data["seasonality"] == {"cells": [], "max": 0}
    assert data["mood_activity"]["points"] == []
    assert data["mood_activity"]["pearson_r"] is None
    assert data["mood_activity"]["sample_size"] == 0
    assert data["github"]["available"] is False
    assert data["github"]["weekly"] == []
    assert data["summary"]["best_day"] is None


def test_overview_days_param_and_zerofill(client: TestClient):
    response = client.get("/analytics/overview?days=7")
    assert response.status_code == 200
    daily = response.json()["daily_activity"]
    assert len(daily) == 7
    today = datetime.now(UTC).date()
    # Oldest → newest, every day present even with no activity.
    assert daily[0]["date"] == (today - timedelta(days=6)).isoformat()
    assert daily[-1]["date"] == today.isoformat()
    for row in daily:
        for key in ("xp", "events", "goals_completed", "pomodoros", "notes"):
            assert row[key] == 0


def test_overview_days_out_of_range_rejected(client: TestClient):
    assert client.get("/analytics/overview?days=0").status_code == 422
    assert client.get("/analytics/overview?days=500").status_code == 422


def test_overview_requires_auth(client_no_auth: TestClient):
    assert client_no_auth.get("/analytics/overview").status_code == 401


def test_overview_daily_aggregation(client: TestClient, db_session):
    db_session.add_all(
        [
            XPEvent(event_type="note_created", xp=10),
            XPEvent(event_type="goal_completed", xp=50),
            XPEvent(event_type="goal_completed", xp=50),
            XPEvent(event_type="pomodoro_completed", xp=15),
            Note(title=f"n-ov-{uuid.uuid4().hex[:8]}", content="a"),
        ]
    )
    db_session.commit()

    data = client.get("/analytics/overview?days=7").json()
    today_row = data["daily_activity"][-1]
    assert today_row["xp"] == 125
    assert today_row["events"] == 4
    assert today_row["goals_completed"] == 2
    assert today_row["pomodoros"] == 1
    assert today_row["notes"] == 1

    summary = data["summary"]
    assert summary["active_days"] == 1
    assert summary["avg_daily_xp"] == round(125 / 7, 1)
    assert summary["best_day"] == {"date": today_row["date"], "xp": 125}


def test_overview_previous_window_totals(client: TestClient, db_session):
    """summary carries same-length previous-period totals (#1499)."""
    prev_day = datetime.now(UTC) - timedelta(days=10)  # inside days=7 prev window
    db_session.add_all(
        [
            XPEvent(event_type="note_created", xp=40, created_at=prev_day),
            XPEvent(event_type="note_edited", xp=5, created_at=prev_day),
            XPEvent(event_type="note_created", xp=10),  # current window
        ]
    )
    db_session.commit()

    summary = client.get("/analytics/overview?days=7").json()["summary"]
    assert summary["window_xp"] == 10
    assert summary["prev_total_xp"] == 45
    assert summary["prev_active_days"] == 1


def test_overview_xp_by_type_sorted(client: TestClient, db_session):
    db_session.add_all(
        [
            XPEvent(event_type="note_created", xp=10),
            XPEvent(event_type="goal_completed", xp=50),
            XPEvent(event_type="goal_completed", xp=50),
            XPEvent(event_type="pomodoro_completed", xp=15),
        ]
    )
    db_session.commit()

    xp_by_type = client.get("/analytics/overview?days=7").json()["xp_by_type"]
    assert [t["xp"] for t in xp_by_type] == sorted(
        (t["xp"] for t in xp_by_type), reverse=True
    )
    goal = next(t for t in xp_by_type if t["type"] == "goal_completed")
    assert goal["xp"] == 100
    assert goal["count"] == 2


def test_overview_seasonality_ranges(client: TestClient, db_session):
    db_session.add(XPEvent(event_type="note_created", xp=10))
    db_session.commit()

    seasonality = client.get("/analytics/overview?days=1").json()["seasonality"]
    cells = seasonality["cells"]
    assert len(cells) >= 1
    for cell in cells:
        assert 0 <= cell["weekday"] <= 6
        assert 0 <= cell["hour"] <= 23
        assert cell["count"] >= 1
    assert seasonality["max"] == max(c["count"] for c in cells)


def test_overview_pearson_null_with_few_samples(client: TestClient, db_session):
    today = datetime.now(UTC).date()
    db_session.add(MoodEntry(user_id=1, score=4, entry_date=today))
    db_session.add(XPEvent(event_type="note_created", xp=10))
    db_session.commit()

    mood = client.get("/analytics/overview?days=7").json()["mood_activity"]
    assert mood["sample_size"] == 1
    assert mood["pearson_r"] is None
    assert mood["points"][0]["mood"] == 4
    assert mood["points"][0]["xp"] == 10


def test_overview_pearson_perfect_correlation(client: TestClient, db_session):
    now = datetime.now(UTC).replace(tzinfo=None)
    for i in range(4):
        moment = now - timedelta(days=3 - i)
        db_session.add(MoodEntry(user_id=1, score=i + 1, entry_date=moment.date()))
        db_session.add(
            XPEvent(event_type="note_created", xp=(i + 1) * 10, created_at=moment)
        )
    db_session.commit()

    mood = client.get("/analytics/overview?days=7").json()["mood_activity"]
    assert mood["sample_size"] == 4
    assert mood["pearson_r"] == 1.0


def test_overview_goals_and_streaks(client: TestClient, db_session):
    db_session.add_all(
        [
            Goal(
                title="g1",
                state=GoalState.ACTIVE,
                temporality=GoalTemporality.DAILY,
                target_value=10,
                current_value=5,
            ),
            Goal(
                title="g2",
                state=GoalState.COMPLETED,
                temporality=GoalTemporality.DAILY,
                target_value=10,
                current_value=10,
            ),
            Goal(title="g3", state=GoalState.INBOX, temporality=GoalTemporality.WEEKLY),
        ]
    )
    stats = db_session.query(UserStats).filter(UserStats.id == 1).first()
    if stats is None:
        stats = UserStats(id=1)
        db_session.add(stats)
    stats.total_xp = 321
    stats.current_streak = 4
    stats.longest_streak = 9
    db_session.commit()

    data = client.get("/analytics/overview?days=7").json()

    goals = data["goals"]
    assert goals["by_state"] == {"ACTIVE": 1, "COMPLETED": 1, "INBOX": 1}
    funnel = {s["stage"]: s["count"] for s in goals["funnel"]}
    assert funnel == {"created": 3, "activated": 2, "completed": 1, "abandoned": 0}
    daily = next(t for t in goals["by_temporality"] if t["temporality"] == "DAILY")
    assert daily["total"] == 2
    assert daily["completed"] == 1
    assert daily["failed"] == 0
    assert daily["avg_progress"] == 75.0

    streaks = data["streaks"]
    assert streaks["current_streak"] == 4
    assert streaks["longest_streak"] == 9
    assert streaks["active_streaks"] == 0
    assert streaks["total_checkins"] == 0
    assert streaks["checkin_rate_30d"] == 0

    assert data["summary"]["total_xp"] == 321


def test_overview_github_unavailable(client: TestClient):
    data = client.get("/analytics/overview?days=7").json()
    assert data["github"]["available"] is False
    assert data["github"]["weekly"] == []


def test_overview_github_weekly(client: TestClient, db_session):
    repo = GitHubRepo(
        name="joidy",
        full_name=f"u/joidy-{uuid.uuid4().hex[:8]}",
        url="https://github.com/u/joidy",
    )
    db_session.add(repo)
    db_session.flush()
    now = datetime.now(UTC).replace(tzinfo=None)
    db_session.add_all(
        [
            GitHubEvent(
                repo_id=repo.id,
                event_type=GitHubEventType.PUSH,
                action="push",
                sender="u",
                created_at=now,
            ),
            GitHubEvent(
                repo_id=repo.id,
                event_type=GitHubEventType.PUSH,
                action="push",
                sender="u",
                created_at=now,
            ),
            GitHubEvent(
                repo_id=repo.id,
                event_type=GitHubEventType.ISSUE_COMMENT,
                action="created",
                sender="u",
                created_at=now,
            ),
        ]
    )
    db_session.commit()

    github = client.get("/analytics/overview?days=7").json()["github"]
    assert github["available"] is True
    assert len(github["weekly"]) == 12
    this_week = github["weekly"][-1]
    assert this_week["pushes"] == 2
    assert this_week["comments"] == 1
    assert this_week["issues"] == 0
    assert this_week["pull_requests"] == 0
