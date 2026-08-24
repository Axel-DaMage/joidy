"""Router tests for the sync conflict endpoints (#13)."""

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from models.note import Note
from models.sync_state import SyncState


def _make_conflicted_note(db_session, title="Conflicted Note"):
    note = Note(title=title, content="local content")
    db_session.add(note)
    db_session.flush()
    sync = SyncState(
        note_id=note.id,
        conflict=True,
        local_mtime=datetime.now(timezone.utc),
        remote_mtime=datetime.now(timezone.utc),
    )
    db_session.add(sync)
    db_session.commit()
    return note.id


def test_list_conflicts_shape(client: TestClient):
    response = client.get("/sync/conflicts")
    assert response.status_code == 200
    data = response.json()
    assert "conflicts" in data
    assert "count" in data
    assert isinstance(data["conflicts"], list)
    assert data["count"] == len(data["conflicts"])


def test_list_conflicts_shows_conflicted_notes(client: TestClient, db_session):
    before = client.get("/sync/conflicts").json()["count"]
    _make_conflicted_note(db_session, "Conflict A Unique")

    response = client.get("/sync/conflicts")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == before + 1
    titles = [c["title"] for c in data["conflicts"]]
    assert "Conflict A Unique" in titles


def test_resolve_keep_local(client: TestClient, db_session):
    note_id = _make_conflicted_note(db_session)

    response = client.post(f"/sync/resolve/{note_id}", json={"resolution": "keep_local"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["resolution"] == "keep_local"

    sync = db_session.query(SyncState).filter(SyncState.note_id == note_id).first()
    assert sync.conflict is False


def test_resolve_merge(client: TestClient, db_session):
    note_id = _make_conflicted_note(db_session)

    response = client.post(f"/sync/resolve/{note_id}", json={
        "resolution": "merge",
        "merged_content": "merged content here",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["resolution"] == "merge"

    note = db_session.query(Note).filter(Note.id == note_id).first()
    assert "merged content here" in note.content


def test_resolve_merge_requires_content(client: TestClient, db_session):
    note_id = _make_conflicted_note(db_session)

    response = client.post(f"/sync/resolve/{note_id}", json={"resolution": "merge"})
    assert response.status_code == 400
    assert "merged_content" in response.json()["detail"]


def test_resolve_invalid_resolution(client: TestClient, db_session):
    note_id = _make_conflicted_note(db_session)

    response = client.post(f"/sync/resolve/{note_id}", json={"resolution": "bogus"})
    assert response.status_code == 422


def test_resolve_nonexistent_note(client: TestClient):
    response = client.post("/sync/resolve/9999", json={"resolution": "keep_local"})
    assert response.status_code == 400


def test_resolve_keep_remote_without_vault(client: TestClient, db_session):
    note_id = _make_conflicted_note(db_session)

    response = client.post(f"/sync/resolve/{note_id}", json={"resolution": "keep_remote"})
    # Without a configured vault path / source_path, the service returns an error
    assert response.status_code == 400
