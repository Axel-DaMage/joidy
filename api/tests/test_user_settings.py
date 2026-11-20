"""Tests for the /user-settings JSON key/value endpoints (#969)."""

import pytest


def test_get_missing_key_returns_null(client):
    resp = client.get("/user-settings/alarms")
    assert resp.status_code == 200
    assert resp.json() == {"key": "alarms", "value": None}


def test_put_then_get_roundtrip(client):
    alarms = [
        {
            "id": "a1",
            "hour": 7,
            "minute": 30,
            "label": "Wake up",
            "days": [1, 2, 3, 4, 5],
            "enabled": True,
            "snoozeMinutes": 10,
            "sound": "beep",
        }
    ]
    resp = client.put("/user-settings/alarms", json={"value": alarms})
    assert resp.status_code == 200
    assert resp.json() == {"key": "alarms", "value": alarms}

    resp = client.get("/user-settings/alarms")
    assert resp.status_code == 200
    assert resp.json()["value"] == alarms


def test_put_overwrites_existing(client):
    client.put("/user-settings/alarms", json={"value": [1, 2, 3]})
    client.put("/user-settings/alarms", json={"value": []})
    resp = client.get("/user-settings/alarms")
    assert resp.json()["value"] == []


def test_put_accepts_scalar_and_null_values(client):
    client.put("/user-settings/volume", json={"value": 0.5})
    assert client.get("/user-settings/volume").json()["value"] == 0.5
    client.put("/user-settings/volume", json={"value": None})
    assert client.get("/user-settings/volume").json()["value"] is None


@pytest.mark.parametrize("bad_key", ["Alarms", "1alarms", "-x", "x" * 64, "a b", "../etc"])
def test_invalid_keys_rejected(client, bad_key):
    resp = client.get(f"/user-settings/{bad_key}")
    assert resp.status_code in (404, 422)
    resp = client.put(f"/user-settings/{bad_key}", json={"value": 1})
    assert resp.status_code in (404, 422)


def test_oversized_value_rejected(client):
    big = "x" * (70 * 1024)
    resp = client.put("/user-settings/blob", json={"value": big})
    assert resp.status_code == 413


def test_storage_is_namespaced(client, db_session):
    """Values must land under the user_settings: prefix in system_config."""
    from models.config import SystemConfig

    client.put("/user-settings/alarms", json={"value": {"a": 1}})
    row = (
        db_session.query(SystemConfig)
        .filter(SystemConfig.key == "user_settings:alarms")
        .first()
    )
    assert row is not None
    # No unprefixed key should exist for the same setting.
    assert (
        db_session.query(SystemConfig).filter(SystemConfig.key == "alarms").first()
        is None
    )


def test_requires_auth(client_no_auth):
    resp = client_no_auth.get("/user-settings/alarms")
    assert resp.status_code == 401
    resp = client_no_auth.put("/user-settings/alarms", json={"value": []})
    assert resp.status_code == 401
