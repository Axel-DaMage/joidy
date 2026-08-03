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
