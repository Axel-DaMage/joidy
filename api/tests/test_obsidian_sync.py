"""Tests for Obsidian sync state and webhook endpoint."""

from datetime import datetime, timezone
from unittest.mock import patch


@patch("config.settings.obsidian_webhook_secret", "super-secret")
def test_obsidian_webhook_requires_secret(client):
    resp = client.post("/webhook/obsidian/legacy?secret=wrong", json={
        "note_id": 1,
        "path": "/vault/note.md",
        "remote_mtime": 1_700_000_000,
    })
    assert resp.status_code == 401


from models.sync_state import SyncState


def _create_note(db_session, note_id):
    """Create a parent Note so SyncState's FK constraint is satisfied on PostgreSQL."""
    from models.note import Note
    note = db_session.query(Note).filter_by(id=note_id).first()
    if note is None:
        note = Note(id=note_id, title=f"Test Note {note_id}", content="", source="obsidian")
        db_session.add(note)
        db_session.commit()
    return note


@patch("config.settings.obsidian_webhook_secret", "")
@patch("config.settings.auth_password", "")
def test_obsidian_webhook_unconfigured_accepts_any(client, db_session):
    _create_note(db_session, 1)
    resp = client.post("/webhook/obsidian/legacy", json={
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


@patch("config.settings.obsidian_webhook_secret", "")
@patch("config.settings.auth_password", "")
def test_obsidian_webhook_detects_conflict(client, db_session):
    _create_note(db_session, 2)
    sync = SyncState(note_id=2, local_mtime=datetime.fromtimestamp(1_600_000_000, tz=timezone.utc))
    db_session.add(sync)
    db_session.commit()

    resp = client.post("/webhook/obsidian/legacy", json={
        "note_id": 2,
        "path": "/vault/note.md",
        "remote_mtime": 1_700_000_000,
    })
    assert resp.status_code == 200
    assert resp.json()["conflict"] is True

    updated = db_session.query(SyncState).filter_by(note_id=2).first()
    assert updated.conflict is True


@patch("config.settings.obsidian_webhook_secret", "")
@patch("config.settings.auth_password", "")
def test_obsidian_webhook_no_conflict_when_mtimes_match(client, db_session):
    _create_note(db_session, 3)
    mtime = 1_700_000_000
    sync = SyncState(
        note_id=3,
        local_mtime=datetime.fromtimestamp(mtime, tz=timezone.utc),
    )
    db_session.add(sync)
    db_session.commit()

    resp = client.post("/webhook/obsidian/legacy", json={
        "note_id": 3,
        "path": "/vault/note.md",
        "remote_mtime": mtime,
    })
    assert resp.status_code == 200
    assert resp.json()["conflict"] is False

    updated = db_session.query(SyncState).filter_by(note_id=3).first()
    assert updated.conflict is False


# ── New webhook endpoint tests (create/update/delete) ──────────────────────────


@patch("config.settings.obsidian_webhook_secret", "")
@patch("config.settings.auth_password", "")
def test_webhook_create_note(client, db_session):
    resp = client.post("/webhook/obsidian", json={
        "event": "create",
        "path": "/vault/webhook-test.md",
        "content": "---\ntitle: Webhook Test\ntags: [python]\n---\n# Hello",
        "mtime": 1_700_000_000,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["action"] == "created"
    assert data["note_id"] is not None

    from models.note import Note
    note = db_session.query(Note).filter_by(source_path="/vault/webhook-test.md").first()
    assert note is not None
    assert note.title == "Webhook Test"
    assert note.source == "obsidian"


@patch("config.settings.obsidian_webhook_secret", "")
@patch("config.settings.auth_password", "")
def test_webhook_update_note(client, db_session):
    # First create
    client.post("/webhook/obsidian", json={
        "event": "create",
        "path": "/vault/update-test.md",
        "content": "original",
    })
    # Then update
    resp = client.post("/webhook/obsidian", json={
        "event": "update",
        "path": "/vault/update-test.md",
        "content": "updated content",
    })
    assert resp.status_code == 200
    assert resp.json()["action"] == "updated"

    from models.note import Note
    note = db_session.query(Note).filter_by(source_path="/vault/update-test.md").first()
    assert note.content == "updated content"


@patch("config.settings.obsidian_webhook_secret", "")
@patch("config.settings.auth_password", "")
def test_webhook_delete_note(client, db_session):
    # First create
    create_resp = client.post("/webhook/obsidian", json={
        "event": "create",
        "path": "/vault/delete-test.md",
        "content": "to be deleted",
    })
    note_id = create_resp.json()["note_id"]

    # Then delete
    resp = client.post("/webhook/obsidian", json={
        "event": "delete",
        "path": "/vault/delete-test.md",
    })
    assert resp.status_code == 200
    assert resp.json()["action"] == "deleted"

    from models.note import Note
    note = db_session.query(Note).filter_by(id=note_id).first()
    assert note is None


@patch("config.settings.obsidian_webhook_secret", "")
@patch("config.settings.auth_password", "")
def test_webhook_delete_unknown_path(client, db_session):
    resp = client.post("/webhook/obsidian", json={
        "event": "delete",
        "path": "/vault/nonexistent.md",
    })
    assert resp.status_code == 200
    assert resp.json()["action"] == "noop"


def test_webhook_invalid_event(client, db_session):
    resp = client.post("/webhook/obsidian", json={
        "event": "invalid",
        "path": "/vault/note.md",
        "content": "test",
    })
    assert resp.status_code == 422


@patch("config.settings.obsidian_webhook_secret", "")
@patch("config.settings.auth_password", "")
def test_webhook_create_missing_content(client, db_session):
    resp = client.post("/webhook/obsidian", json={
        "event": "create",
        "path": "/vault/note.md",
    })
    assert resp.status_code == 400


@patch("config.settings.obsidian_webhook_secret", "test-secret")
def test_webhook_new_endpoint_requires_secret(client, db_session):
    resp = client.post("/webhook/obsidian", json={
        "event": "create",
        "path": "/vault/secret-test.md",
        "content": "test",
    })
    assert resp.status_code == 401


@patch("config.settings.obsidian_webhook_secret", "test-secret")
def test_webhook_new_endpoint_with_valid_secret(client, db_session):
    resp = client.post("/webhook/obsidian?secret=test-secret", json={
        "event": "create",
        "path": "/vault/valid-secret.md",
        "content": "test content",
    })
    assert resp.status_code == 200
    assert resp.json()["action"] == "created"


@patch("config.settings.obsidian_webhook_secret", "")
@patch("config.settings.auth_password", "hashed-password")
def test_webhook_jwt_fallback_rejects_no_token(client, db_session):
    """In production with auth_password set, webhook requires JWT when no secret configured."""
    resp = client.post("/webhook/obsidian", json={
        "event": "create",
        "path": "/vault/jwt-fallback.md",
        "content": "test",
    })
    assert resp.status_code == 401


@patch("config.settings.obsidian_webhook_secret", "")
@patch("config.settings.auth_password", "hashed-password")
def test_webhook_jwt_fallback_rejects_invalid_token(client, db_session):
    """Invalid JWT token is rejected when no webhook secret configured."""
    resp = client.post(
        "/webhook/obsidian",
        json={
            "event": "create",
            "path": "/vault/jwt-invalid.md",
            "content": "test",
        },
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert resp.status_code == 401
