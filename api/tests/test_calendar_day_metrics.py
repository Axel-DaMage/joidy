"""Tests for GET /calendar/day-metrics — per-day intelligence badges (#1658)."""

import datetime as dt
import json

from fastapi.testclient import TestClient
from models.gamification import StreakRecord, XPEvent
from models.mood_entry import MoodEntry
from models.note import Note

START = "2099-07-01"
END = "2099-07-31"


def _metrics(client: TestClient, start: str = START, end: str = END):
    return client.get(f"/calendar/day-metrics?start={start}&end={end}")


def test_day_metrics_empty_range(client: TestClient):
    response = _metrics(client)
    assert response.status_code == 200
    days = response.json()
    assert len(days) == 31
    assert days[0]["date"] == "2099-07-01"
    assert days[-1]["date"] == "2099-07-31"
    assert all(d["xp"] == 0 and d["notes"] == 0 and d["mood_score"] is None for d in days)
    assert all(d["streak_day"] is False for d in days)


def test_day_metrics_requires_valid_dates(client: TestClient):
    assert _metrics(client, start="nope").status_code == 400
    assert _metrics(client, start="2099-07-10", end="2099-07-01").status_code == 400
    # Over the 370-day cap (year view is the largest legitimate range).
    assert _metrics(client, start="2098-01-01", end="2099-12-31").status_code == 400


def test_day_metrics_full_year_allowed(client: TestClient):
    """The year view legitimately requests a whole year of density dots."""
    response = _metrics(client, start="2099-01-01", end="2099-12-31")
    assert response.status_code == 200
    assert len(response.json()) == 365


def test_day_metrics_aggregates_sources(client: TestClient, db_session):
    day = dt.datetime(2099, 7, 15, 12, 0, 0)
    db_session.add_all(
        [
            XPEvent(
                event_type="note_created",
                xp=10,
                created_at=day,
            ),
            XPEvent(
                event_type="pomodoro_completed",
                xp=15,
                metadata_json=json.dumps({"pomodoro_id": "p1", "duration_minutes": 25}),
                created_at=day,
            ),
            XPEvent(
                event_type="pomodoro_completed",
                xp=15,
                metadata_json=json.dumps({"pomodoro_id": "p2", "duration_minutes": 50}),
                created_at=day,
            ),
            XPEvent(
                event_type="goal_completed",
                xp=50,
                created_at=day,
            ),
            StreakRecord(activity_date=dt.date(2099, 7, 15), xp_earned=90),
            MoodEntry(user_id=1, score=4, entry_date=dt.date(2099, 7, 15)),
            Note(title="A note", created_at=day),
        ]
    )
    db_session.commit()

    response = _metrics(client)
    assert response.status_code == 200
    row = next(d for d in response.json() if d["date"] == "2099-07-15")
    assert row["xp"] == 90
    assert row["xp_events"] == 4
    assert row["pomodoros"] == 2
    assert row["focus_minutes"] == 75
    assert row["goals_completed"] == 1
    assert row["notes"] == 1
    assert row["mood_score"] == 4
    assert row["streak_day"] is True


def test_day_metrics_pomodoro_bad_metadata_tolerated(client: TestClient, db_session):
    """Unparseable/missing duration metadata counts the pomodoro but 0 minutes."""
    day = dt.datetime(2099, 7, 16, 9, 0, 0)
    db_session.add_all(
        [
            XPEvent(event_type="pomodoro_completed", xp=15, metadata_json="not-json", created_at=day),
            XPEvent(event_type="pomodoro_completed", xp=15, metadata_json="{}", created_at=day),
        ]
    )
    db_session.commit()
    row = next(d for d in _metrics(client).json() if d["date"] == "2099-07-16")
    assert row["pomodoros"] == 2
    assert row["focus_minutes"] == 0
