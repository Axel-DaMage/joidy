"""Tests for Obsidian sync state and webhook endpoint."""

from datetime import datetime, timezone
from unittest.mock import patch


@patch("config.settings.obsidian_webhook_secret", "super-secret")
def test_obsidian_webhook_requires_secret(client):
    resp = client.post("/webhook/obsidian?secret=wrong", json={
        "note_id": 1,
        "path": "/vault/note.md",
        "remote_mtime": 1_700_000_000,
    })
    assert resp.status_code == 401


from models.sync_state import SyncState


def test_obsidian_webhook_unconfigured_accepts_any(client, db_session):
    resp = client.post("/webhook/obsidian", json={
        "note_id": 1,
        "path": "/vault/note.md",
        "remote_mtime": 1_700_000_000,
    })
    assert resp.status_code == 200

    sync = db_session.query(SyncState).filter_by(note_id=1).first()
    assert sync is not None
    assert sync.remote_mtime is not None
    assert sync.remote_mtime.timestamp() == 1_700_000_000


def test_sync_state_model_exists():
    assert SyncState.__tablename__ == "sync_state"


def test_obsidian_webhook_detects_conflict(client, db_session):
    sync = SyncState(note_id=2, local_mtime=datetime.fromtimestamp(1_600_000_000, tz=timezone.utc))
    db_session.add(sync)
    db_session.commit()

    resp = client.post("/webhook/obsidian", json={
        "note_id": 2,
        "path": "/vault/note.md",
        "remote_mtime": 1_700_000_000,
    })
    assert resp.status_code == 200
    assert resp.json()["conflict"] is True

    updated = db_session.query(SyncState).filter_by(note_id=2).first()
    assert updated.conflict is True


def test_obsidian_webhook_no_conflict_when_mtimes_match(client, db_session):
    mtime = 1_700_000_000
    sync = SyncState(
        note_id=3,
        local_mtime=datetime.fromtimestamp(mtime, tz=timezone.utc),
    )
    db_session.add(sync)
    db_session.commit()

    resp = client.post("/webhook/obsidian", json={
        "note_id": 3,
        "path": "/vault/note.md",
        "remote_mtime": mtime,
    })
    assert resp.status_code == 200
    assert resp.json()["conflict"] is False

    updated = db_session.query(SyncState).filter_by(note_id=3).first()
    assert updated.conflict is False
