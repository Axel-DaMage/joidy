"""Tests for GET /notes/source-paths — the vault worker's bulk existence
check (#1535).

The worker's initial scan calls this once per (re)start to verify which
``source_path`` values the API actually holds before trusting its persisted
fingerprints — that sqlite store survives ``dev-reset``/backup restores, so
a fingerprint match alone cannot prove a note still exists.
"""

import pytest
from config import settings


@pytest.fixture
def vault(tmp_path, monkeypatch):
    """Point the effective vault root at a per-test temp dir."""
    monkeypatch.setattr(settings, "obsidian_vault_path", str(tmp_path))
    return tmp_path


def test_source_paths_lists_only_path_backed_notes(client, db_session, vault):
    a = client.post(
        "/notes/",
        json={"title": "a", "content": "x", "source": "api", "source_path": f"{vault}/a.md"},
    )
    assert a.status_code == 201
    b = client.post(
        "/notes/",
        json={"title": "b", "content": "x", "source": "api", "source_path": f"{vault}/b.md"},
    )
    assert b.status_code == 201
    c = client.post("/notes/", json={"title": "c", "content": "x", "source": "api"})
    assert c.status_code == 201

    resp = client.get("/notes/source-paths")

    assert resp.status_code == 200
    assert sorted(resp.json()) == sorted([f"{vault}/a.md", f"{vault}/b.md"])


def test_source_paths_is_not_parsed_as_note_id(client):
    """Registered before /notes/{note_id}, the literal segment must hit the
    list endpoint, not a 422 on the id converter."""
    resp = client.get("/notes/source-paths")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_source_paths_empty_when_no_vault_notes(client):
    resp = client.get("/notes/source-paths")
    assert resp.status_code == 200
    assert resp.json() == []
