"""Tests for /vault router endpoints (#13).

The vault writer service touches the filesystem (Obsidian vault), so the
service functions are mocked to test the router layer in isolation. This
covers the write-daily, write-objectives, write-skills, and restore-goals
endpoints for both success and no-vault paths.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient


@patch("routers.vault.write_daily", return_value=True)
def test_vault_write_daily_ok(mock_write, client: TestClient):
    resp = client.post("/vault/write-daily")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["file"].startswith("_joidy/daily/")
    assert data["file"].endswith(".md")
    mock_write.assert_called_once()


@patch("routers.vault.write_daily", return_value=False)
def test_vault_write_daily_no_vault(mock_write, client: TestClient):
    resp = client.post("/vault/write-daily")
    assert resp.status_code == 200
    assert resp.json()["status"] == "no_vault"
    mock_write.assert_called_once()


@patch("routers.vault.write_objectives", return_value=True)
def test_vault_write_objectives_ok(mock_write, client: TestClient):
    resp = client.post("/vault/write-objectives")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    mock_write.assert_called_once()


@patch("routers.vault.write_objectives", return_value=False)
def test_vault_write_objectives_no_vault(mock_write, client: TestClient):
    resp = client.post("/vault/write-objectives")
    assert resp.status_code == 200
    assert resp.json()["status"] == "no_vault"
    mock_write.assert_called_once()


@patch("routers.vault.write_skills", return_value=True)
def test_vault_write_skills_ok(mock_write, client: TestClient):
    resp = client.post("/vault/write-skills")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    mock_write.assert_called_once()


@patch("routers.vault.write_skills", return_value=False)
def test_vault_write_skills_no_vault(mock_write, client: TestClient):
    resp = client.post("/vault/write-skills")
    assert resp.status_code == 200
    assert resp.json()["status"] == "no_vault"
    mock_write.assert_called_once()


@patch(
    "routers.vault.restore_goals_from_vault",
    return_value={"status": "ok", "restored": 2, "skipped": 1},
)
def test_vault_restore_goals(mock_restore, client: TestClient):
    resp = client.post("/vault/restore-goals")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["restored"] == 2
    assert data["skipped"] == 1
    mock_restore.assert_called_once()


@patch(
    "routers.vault.restore_goals_from_vault",
    return_value={"status": "no_vault", "restored": 0, "skipped": 0},
)
def test_vault_restore_goals_no_vault(mock_restore, client: TestClient):
    resp = client.post("/vault/restore-goals")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "no_vault"
    assert data["restored"] == 0
