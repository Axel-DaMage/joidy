"""Tests for Obsidian sync state and webhook endpoint."""

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
