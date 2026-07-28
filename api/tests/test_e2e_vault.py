"""E2E tests for vault/sync API endpoints and Obsidian import flow."""

from fastapi.testclient import TestClient


def test_vault_write_daily_returns_ok(client: TestClient):
    """The endpoint may return 'no_vault' if VAULT_PATH is unset, but should not error."""
    resp = client.post("/vault/write-daily")
    assert resp.status_code == 200
    assert resp.json()["status"] in ("ok", "no_vault")


def test_vault_write_objectives_returns_ok(client: TestClient):
    resp = client.post("/vault/write-objectives")
    assert resp.status_code == 200
    assert resp.json()["status"] in ("ok", "no_vault")


def test_vault_write_skills_returns_ok(client: TestClient):
    resp = client.post("/vault/write-skills")
    assert resp.status_code == 200
    assert resp.json()["status"] in ("ok", "no_vault")


# ─── Obsidian import flow ────────────────────────────────────────────────────


def test_create_note_with_obsidian_source(client: TestClient):
    """Simulate vault watcher importing a note."""
    payload = {
        "title": "Obsidian Note",
        "content": "Imported from vault",
        "tags": ["imported"],
        "source": "obsidian",
        "source_path": "/vault/test-obsidian-note.md",
    }
    resp = client.post("/notes/", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["source"] == "obsidian"
    assert data["source_path"] == "/vault/test-obsidian-note.md"


def test_imported_note_found_by_source_path(client: TestClient):
    client.post("/notes/", json={
        "title": "Path Find", "content": "X", "tags": [],
        "source": "obsidian", "source_path": "/vault/find-me.md",
    })
    resp = client.get("/notes/")
    assert resp.status_code == 200
    notes = resp.json()
    match = [n for n in notes if n.get("source_path") == "/vault/find-me.md"]
    assert len(match) == 1


def test_update_imported_note_content(client: TestClient):
    create = client.post("/notes/", json={
        "title": "Obs Upd", "content": "Old", "tags": [],
        "source": "obsidian", "source_path": "/vault/update-test.md",
    }).json()
    resp = client.put(f"/notes/{create['id']}", json={
        "content": "Updated via watcher",
        "tags": ["updated"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "updated" in data["tags"]


def test_rebuild_derived_data(client: TestClient):
    resp = client.post("/notes/rebuild-derived")
    assert resp.status_code == 202


def test_tag_graph_after_import(client: TestClient):
    client.post("/notes/", json={
        "title": "Graph Test", "content": "#tag-a and #tag-b", "tags": ["tag-a", "tag-b"],
        "source": "obsidian", "source_path": "/vault/graph-test.md",
    })
    resp = client.get("/tags/graph")
    assert resp.status_code == 200
