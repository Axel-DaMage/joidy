"""Tests for GET /achievements and POST /achievements/unlock (#1137).

Contract: unlocks are idempotent per (user_id, achievement_key), GET only
returns the authenticated user's rows, and payloads are validated.

Like test_routers_gamification_pomodoro.py, assertions filter by per-test
unique achievement keys: committed rows can leak between tests on the local
SQLite fallback (the wipe only runs against Postgres test DBs).
"""

import json
from uuid import uuid4

from fastapi.testclient import TestClient
from models.achievement import Achievement


def _unique_key(prefix: str = "ach") -> str:
    return f"{prefix}-{uuid4().hex[:10]}"


def test_unlock_creates_and_is_idempotent(client: TestClient, db_session):
    key = _unique_key()
    payload = {"achievement_key": key}

    first = client.post("/achievements/unlock", json=payload)
    assert first.status_code == 200
    body = first.json()
    assert body["achievement_key"] == key
    assert body["already_unlocked"] is False
    assert body["unlocked_at"]

    replay = client.post("/achievements/unlock", json=payload)
    assert replay.status_code == 200
    replay_body = replay.json()
    assert replay_body["already_unlocked"] is True
    assert replay_body["unlocked_at"] == body["unlocked_at"]

    rows = db_session.query(Achievement).filter(Achievement.achievement_key == key).all()
    assert len(rows) == 1


def test_unlock_preserves_client_timestamp_and_metadata(client: TestClient, db_session):
    key = _unique_key()
    res = client.post(
        "/achievements/unlock",
        json={
            "achievement_key": key,
            "unlocked_at": "2026-01-15T10:30:00Z",
            "metadata": {"source": "streak"},
        },
    )
    assert res.status_code == 200
    body = res.json()
    # TIMESTAMP columns are naive: the stored wall-clock survives the round
    # trip but the UTC offset does not.
    assert body["unlocked_at"].startswith("2026-01-15T10:30:00")
    assert body["metadata"] == {"source": "streak"}

    row = db_session.query(Achievement).filter(Achievement.achievement_key == key).first()
    assert row is not None
    assert json.loads(row.metadata_json) == {"source": "streak"}


def test_unlock_replay_does_not_overwrite_original_data(client: TestClient, db_session):
    key = _unique_key()
    first = client.post(
        "/achievements/unlock",
        json={"achievement_key": key, "unlocked_at": "2026-01-01T00:00:00Z"},
    )
    replay = client.post(
        "/achievements/unlock",
        json={"achievement_key": key, "unlocked_at": "2026-06-01T00:00:00Z"},
    )
    assert replay.status_code == 200
    assert replay.json()["already_unlocked"] is True
    assert replay.json()["unlocked_at"].startswith("2026-01-01T00:00:00")

    rows = db_session.query(Achievement).filter(Achievement.achievement_key == key).all()
    assert len(rows) == 1


def test_get_returns_only_current_user_achievements(client: TestClient, db_session):
    mine = _unique_key("mine")
    theirs = _unique_key("theirs")
    db_session.add(Achievement(user_id=1, achievement_key=mine))
    db_session.add(Achievement(user_id=2, achievement_key=theirs))
    db_session.commit()

    res = client.get("/achievements")
    assert res.status_code == 200
    records = res.json()
    keys = [a["achievement_key"] for a in records]
    assert mine in keys
    assert theirs not in keys
    assert all(a["user_id"] == 1 for a in records)


def test_unlock_validates_payload(client: TestClient):
    assert client.post("/achievements/unlock", json={}).status_code == 422
    assert client.post("/achievements/unlock", json={"achievement_key": ""}).status_code == 422
    assert (
        client.post("/achievements/unlock", json={"achievement_key": "x" * 101}).status_code
        == 422
    )
    assert (
        client.post(
            "/achievements/unlock", json={"achievement_key": "ok", "unlocked_at": "not-a-date"}
        ).status_code
        == 422
    )


def test_unlock_requires_auth(client_no_auth: TestClient):
    res = client_no_auth.post("/achievements/unlock", json={"achievement_key": "first_note"})
    assert res.status_code == 401


def test_list_requires_auth(client_no_auth: TestClient):
    res = client_no_auth.get("/achievements")
    assert res.status_code == 401
