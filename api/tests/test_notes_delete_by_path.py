"""Tests for DELETE /notes/by-path — atomic source_path delete (#1302).

The vault watcher deletes notes through this endpoint: the match and the
delete run inside one SELECT ... FOR UPDATE-locked transaction, and an
optional ``expected_updated_at`` etag refuses (409) to remove a note that
changed or was recreated between the watcher's lookup and the delete —
closing the list-then-delete TOCTOU.
"""

import pytest
from config import settings


@pytest.fixture
def vault(tmp_path, monkeypatch):
    """Point the effective vault root at a per-test temp dir."""
    monkeypatch.setattr(settings, "obsidian_vault_path", str(tmp_path))
    return tmp_path


def _create_vault_note(client, path: str) -> dict:
    resp = client.post(
        "/notes/",
        json={"title": "t", "content": "body", "source": "obsidian", "source_path": path},
    )
    assert resp.status_code == 201
    return resp.json()


def test_delete_by_path_removes_matching_note(client, db_session, vault):
    path = f"{vault}/gone.md"
    note = _create_vault_note(client, path)

    resp = client.delete(
        "/notes/by-path",
        params={"source_path": path, "expected_updated_at": note["updated_at"]},
    )

    assert resp.status_code == 200
    assert resp.json()["deleted"] == note["id"]
    from models.note import Note

    assert db_session.query(Note).filter_by(id=note["id"]).first() is None


def test_delete_by_path_without_etag_deletes(client, db_session, vault):
    """The etag is optional — an omitted check deletes unconditionally."""
    path = f"{vault}/plain.md"
    note = _create_vault_note(client, path)

    resp = client.delete("/notes/by-path", params={"source_path": path})

    assert resp.status_code == 200
    from models.note import Note

    assert db_session.query(Note).filter_by(id=note["id"]).first() is None


def test_delete_by_path_stale_etag_refused(client, db_session, vault):
    """A mismatched etag means the note changed (or was recreated) since the
    lookup — the delete must be refused, not applied to the wrong note."""
    path = f"{vault}/conflicted.md"
    note = _create_vault_note(client, path)

    resp = client.delete(
        "/notes/by-path",
        params={"source_path": path, "expected_updated_at": "2000-01-01T00:00:00Z"},
    )

    assert resp.status_code == 409
    from models.note import Note

    assert db_session.query(Note).filter_by(id=note["id"]).first() is not None


def test_delete_by_path_unparseable_etag_refused(client, db_session, vault):
    """Fail closed: a malformed etag is treated as a conflict, never as a
    reason to skip the check and delete anyway."""
    path = f"{vault}/bad-etag.md"
    note = _create_vault_note(client, path)

    resp = client.delete(
        "/notes/by-path",
        params={"source_path": path, "expected_updated_at": "not-a-date"},
    )

    assert resp.status_code == 409
    from models.note import Note

    assert db_session.query(Note).filter_by(id=note["id"]).first() is not None


def test_delete_by_path_unknown_note_404(client, vault):
    resp = client.delete("/notes/by-path", params={"source_path": f"{vault}/missing.md"})
    assert resp.status_code == 404


def test_delete_by_path_outside_vault_400(client, vault):
    """Paths resolving outside the vault get the same generic 400 as the
    write-side validation — no file-existence oracle (#1314)."""
    resp = client.delete("/notes/by-path", params={"source_path": "/etc/outside.md"})
    assert resp.status_code == 400


def test_delete_by_path_joidy_dir_400(client, vault):
    resp = client.delete("/notes/by-path", params={"source_path": f"{vault}/_joidy/daily.md"})
    assert resp.status_code == 400
