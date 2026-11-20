"""Tests for GET /achievements and POST /achievements/unlock (#1137, #1320).

Contract: unlocks are idempotent per (user_id, achievement_key), GET only
returns the authenticated user's rows, and payloads are validated. Since
#1320 the key must exist in the server-side catalog and its precondition
must be verifiably met — clients can neither mint unearned achievements nor
backdate ``unlocked_at``.
"""

import json
from uuid import uuid4

from fastapi.testclient import TestClient
from models.achievement import Achievement
from models.note import Note


def _unique_key(prefix: str = "ach") -> str:
    return f"{prefix}-{uuid4().hex[:10]}"


def _make_note(db_session, title: str = "Nota") -> Note:
    note = Note(title=title, content="contenido")
    db_session.add(note)
    db_session.commit()
    db_session.refresh(note)
    return note


def test_unlock_creates_and_is_idempotent(client: TestClient, db_session):
    _make_note(db_session)
    payload = {"achievement_key": "first_note"}

    first = client.post("/achievements/unlock", json=payload)
    assert first.status_code == 200
    body = first.json()
    assert body["achievement_key"] == "first_note"
    assert body["already_unlocked"] is False
    assert body["unlocked_at"]

    replay = client.post("/achievements/unlock", json=payload)
    assert replay.status_code == 200
    replay_body = replay.json()
    assert replay_body["already_unlocked"] is True
    assert replay_body["unlocked_at"] == body["unlocked_at"]

    rows = db_session.query(Achievement).filter(Achievement.achievement_key == "first_note").all()
    assert len(rows) == 1


def test_unlock_ignores_client_timestamp_and_stores_metadata(client: TestClient, db_session):
    """#1320 — a forged ``unlocked_at`` must never reach the DB."""
    _make_note(db_session)
    res = client.post(
        "/achievements/unlock",
        json={
            "achievement_key": "first_note",
            "unlocked_at": "2026-01-15T10:30:00Z",
            "metadata": {"source": "streak"},
        },
    )
    assert res.status_code == 200
    body = res.json()
    # The server stamps its own timestamp; the 2026-01-15 backdate is ignored.
    assert not body["unlocked_at"].startswith("2026-01-15")
    assert body["metadata"] == {"source": "streak"}

    row = db_session.query(Achievement).filter(Achievement.achievement_key == "first_note").first()
    assert row is not None
    assert json.loads(row.metadata_json) == {"source": "streak"}


def test_unlock_replay_does_not_overwrite_original_data(client: TestClient, db_session):
    _make_note(db_session)
    first = client.post("/achievements/unlock", json={"achievement_key": "first_note"})
    original_unlocked_at = first.json()["unlocked_at"]

    replay = client.post(
        "/achievements/unlock",
        json={
            "achievement_key": "first_note",
            "unlocked_at": "2026-06-01T00:00:00Z",
            "metadata": {"tampered": True},
        },
    )
    assert replay.status_code == 200
    assert replay.json()["already_unlocked"] is True
    assert replay.json()["unlocked_at"] == original_unlocked_at

    rows = db_session.query(Achievement).filter(Achievement.achievement_key == "first_note").all()
    assert len(rows) == 1


def test_unlock_rejects_unknown_key(client: TestClient):
    """#1320 — arbitrary keys (e.g. a forged 'streak_365') are not unlockable."""
    res = client.post("/achievements/unlock", json={"achievement_key": "streak_365"})
    assert res.status_code == 400
    assert res.json()["detail"] == "Unknown achievement key"

    res = client.post("/achievements/unlock", json={"achievement_key": _unique_key()})
    assert res.status_code == 400


def test_unlock_rejects_unearned_catalog_key(client: TestClient):
    """#1320 — catalog keys require verifiable preconditions."""
    # No notes/goals/streak in the test DB → criteria unmet.
    assert client.post("/achievements/unlock", json={"achievement_key": "fifty_notes"}).status_code == 403
    assert client.post("/achievements/unlock", json={"achievement_key": "week_streak"}).status_code == 403
    assert client.post("/achievements/unlock", json={"achievement_key": "plant_tree"}).status_code == 403


def test_unlock_verifies_precondition_counts(client: TestClient, db_session):
    """ten_notes must fail at 9 notes and succeed at 10."""
    import pytest

    baseline = db_session.query(Note).count()
    if baseline >= 10:
        pytest.skip("committed notes leaked from another test (SQLite fallback)")
    for i in range(9 - baseline):
        _make_note(db_session, f"Nota {i}")
    assert client.post("/achievements/unlock", json={"achievement_key": "ten_notes"}).status_code == 403

    _make_note(db_session, "Nota extra")
    res = client.post("/achievements/unlock", json={"achievement_key": "ten_notes"})
    assert res.status_code == 200
    assert res.json()["already_unlocked"] is False


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
    assert client.post("/achievements/unlock", json={"achievement_key": "x" * 101}).status_code == 422
    assert (
        client.post("/achievements/unlock", json={"achievement_key": "ok", "unlocked_at": "not-a-date"}).status_code
        == 422
    )


def test_unlock_metadata_is_bounded(client: TestClient):
    res = client.post(
        "/achievements/unlock",
        json={"achievement_key": "first_note", "metadata": {"blob": "x" * 3000}},
    )
    assert res.status_code == 422


def test_unlock_requires_auth(client_no_auth: TestClient):
    res = client_no_auth.post("/achievements/unlock", json={"achievement_key": "first_note"})
    assert res.status_code == 401


def test_list_requires_auth(client_no_auth: TestClient):
    res = client_no_auth.get("/achievements")
    assert res.status_code == 401
