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
    assert os.path.isdir(os.path.join(vault, "notes", "daily"))
