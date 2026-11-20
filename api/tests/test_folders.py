"""Tests for folders router security and path validation."""

import os

from config import settings


def test_create_folder_requires_auth(client_no_auth):
    resp = client_no_auth.post("/folders/", json={"path": "test-folder"})
    assert resp.status_code == 401


def test_delete_folder_requires_auth(client_no_auth):
    resp = client_no_auth.delete("/folders/test-folder")
    assert resp.status_code == 401


def test_create_folder_path_traversal(client, monkeypatch, tmp_path):
    vault = str(tmp_path / "vault")
    os.makedirs(vault, exist_ok=True)
    monkeypatch.setattr(settings, "obsidian_vault_path", vault)

    resp = client.post("/folders/", json={"path": "../outside"})
    assert resp.status_code == 400


def test_create_folder_success(client, monkeypatch, tmp_path):
    vault = str(tmp_path / "vault")
    os.makedirs(vault, exist_ok=True)
    monkeypatch.setattr(settings, "obsidian_vault_path", vault)

    resp = client.post("/folders/", json={"path": "notes/daily"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "path": "notes/daily"}
    assert os.path.isdir(os.path.join(vault, "notes", "daily"))


def test_create_folder_already_exists(client, monkeypatch, tmp_path):
    vault = str(tmp_path / "vault")
    os.makedirs(vault, exist_ok=True)
    monkeypatch.setattr(settings, "obsidian_vault_path", vault)

    # Pre-create the folder so the endpoint sees it as existing.
    os.makedirs(os.path.join(vault, "existing-folder"), exist_ok=True)

    resp = client.post("/folders/", json={"path": "existing-folder"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Folder already exists"


def test_create_folder_no_vault_path(client, monkeypatch):
    """When OBSIDIAN_VAULT_PATH is not set, folder creation returns 400."""
    monkeypatch.setattr(settings, "obsidian_vault_path", "")

    resp = client.post("/folders/", json={"path": "some-folder"})
    assert resp.status_code == 400
    assert "OBSIDIAN_VAULT_PATH" in resp.json()["detail"]


def test_create_folder_invalid_name(client, monkeypatch, tmp_path):
    vault = str(tmp_path / "vault")
    os.makedirs(vault, exist_ok=True)
    monkeypatch.setattr(settings, "obsidian_vault_path", vault)

    for bad in ["bad\\name", "bad:name", "bad*name", "../escape", ".", "..", "a//b"]:
        resp = client.post("/folders/", json={"path": bad})
        assert resp.status_code == 400, f"expected 400 for {bad!r}"
        assert resp.json()["detail"] == "Invalid folder name"


def test_create_folder_name_too_long(client, monkeypatch, tmp_path):
    vault = str(tmp_path / "vault")
    os.makedirs(vault, exist_ok=True)
    monkeypatch.setattr(settings, "obsidian_vault_path", vault)

    resp = client.post("/folders/", json={"path": "a" * 256})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Folder name too long"


def test_list_folders_requires_auth(client_no_auth):
    resp = client_no_auth.get("/folders/")
    assert resp.status_code == 401


def test_list_folders_empty(client, monkeypatch, tmp_path):
    vault = str(tmp_path / "vault")
    os.makedirs(vault, exist_ok=True)
    monkeypatch.setattr(settings, "obsidian_vault_path", vault)

    resp = client.get("/folders/")
    assert resp.status_code == 200
    assert resp.json() == {"folders": []}


def test_list_folders_returns_nested_and_skips_internal(client, monkeypatch, tmp_path):
    vault = str(tmp_path / "vault")
    os.makedirs(os.path.join(vault, "Proyectos", "Sub"), exist_ok=True)
    os.makedirs(os.path.join(vault, "Notas"), exist_ok=True)
    os.makedirs(os.path.join(vault, "_joidy", "daily"), exist_ok=True)
    os.makedirs(os.path.join(vault, ".obsidian"), exist_ok=True)
    monkeypatch.setattr(settings, "obsidian_vault_path", vault)

    resp = client.get("/folders/")
    assert resp.status_code == 200
    assert resp.json()["folders"] == ["Notas", "Proyectos", "Proyectos/Sub"]


def test_list_folders_no_vault_path(client, monkeypatch):
    monkeypatch.setattr(settings, "obsidian_vault_path", "")

    resp = client.get("/folders/")
    assert resp.status_code == 400
    assert "OBSIDIAN_VAULT_PATH" in resp.json()["detail"]


def test_delete_folder_success(client, monkeypatch, tmp_path):
    vault = str(tmp_path / "vault")
    os.makedirs(vault, exist_ok=True)
    monkeypatch.setattr(settings, "obsidian_vault_path", vault)

    # Create a folder to delete.
    folder = os.path.join(vault, "to-delete")
    os.makedirs(folder, exist_ok=True)

    resp = client.delete("/folders/to-delete")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert not os.path.exists(folder)


def test_delete_folder_not_found(client, monkeypatch, tmp_path):
    vault = str(tmp_path / "vault")
    os.makedirs(vault, exist_ok=True)
    monkeypatch.setattr(settings, "obsidian_vault_path", vault)

    resp = client.delete("/folders/nonexistent-folder")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Folder not found"


def test_delete_folder_vault_root_rejected(client, monkeypatch, tmp_path):
    """Paths resolving to the vault root must not rmtree the vault (#1313).

    "." and ".."-style segments (literal or %2e%2e-decoded by the router) all
    resolve to the vault itself; the delete must be rejected and the vault
    left untouched.
    """
    vault = str(tmp_path / "vault")
    os.makedirs(os.path.join(vault, "keep"), exist_ok=True)
    monkeypatch.setattr(settings, "obsidian_vault_path", vault)

    for url in ("/folders/.", "/folders/x/..", "/folders/x/y/../..", "/folders/a/%2e%2e"):
        resp = client.delete(url)
        assert resp.status_code == 400, f"expected 400 for {url!r}"

    assert os.listdir(vault) == ["keep"]


def test_delete_folder_hidden_or_internal_rejected(client, monkeypatch, tmp_path):
    """Dirs pruned from listing must be undeletable through the API (#1313).

    _list_vault_folders hides dot-dirs and "_joidy" at any depth; allowing
    DELETE on them would let the API destroy Obsidian config, git history or
    internal state it never exposes.
    """
    protected = (".obsidian", ".git", ".trash", "_joidy", "parent/.hidden", "sub/_joidy")
    vault = str(tmp_path / "vault")
    for rel in protected:
        os.makedirs(os.path.join(vault, rel), exist_ok=True)
    monkeypatch.setattr(settings, "obsidian_vault_path", vault)

    for rel in protected:
        resp = client.delete(f"/folders/{rel}")
        assert resp.status_code == 400, f"expected 400 for {rel!r}"
        assert os.path.isdir(os.path.join(vault, rel))


def test_delete_folder_symlink_to_vault_root_rejected(client, monkeypatch, tmp_path):
    """A symlinked dir whose realpath is the vault root is depth-0 (#1313).

    Name validation cannot catch this: "link" is a valid folder name — only
    the realpath-equals-vault guard rejects it.
    """
    vault = str(tmp_path / "vault")
    os.makedirs(os.path.join(vault, "keep"), exist_ok=True)
    link = os.path.join(vault, "link")
    os.symlink(vault, link)
    monkeypatch.setattr(settings, "obsidian_vault_path", vault)

    resp = client.delete("/folders/link")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Cannot target the vault root"
    assert os.path.isdir(os.path.join(vault, "keep"))
    assert os.path.islink(link)


def test_create_folder_hidden_or_internal_rejected(client, monkeypatch, tmp_path):
    """Create shares the denylist: hidden/internal dirs stay untouchable (#1313)."""
    vault = str(tmp_path / "vault")
    os.makedirs(vault, exist_ok=True)
    monkeypatch.setattr(settings, "obsidian_vault_path", vault)

    for bad in (".obsidian", "_joidy", "parent/.hidden"):
        resp = client.post("/folders/", json={"path": bad})
        assert resp.status_code == 400, f"expected 400 for {bad!r}"
        assert not os.path.exists(os.path.join(vault, bad))
