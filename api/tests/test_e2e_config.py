"""E2E tests for the /config endpoints.

Regression coverage for #199: POST /config used to raise NameError because
`settings` was not imported in `api/routers/config.py`, returning a 500.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

import routers.config as config_router


def test_get_config_returns_200(client: TestClient):
    resp = client.get("/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "configured_keys" in data


def test_post_config_returns_200_not_500(client: TestClient):
    """POST /config must not raise NameError on the in-memory settings update."""
    fake_env = {"OBSIDIAN_VAULT_PATH": "/tmp/vault"}

    with patch.object(config_router, "read_env", return_value=dict(fake_env)), \
         patch.object(config_router, "write_env") as mock_write:
        resp = client.post("/config", json={"obsidian_vault_path": "/tmp/new_vault"})

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    mock_write.assert_called_once()
    # The new value must be persisted to the env dict passed to write_env
    written = mock_write.call_args.args[0]
    assert written["OBSIDIAN_VAULT_PATH"] == "/tmp/new_vault"
