"""Tests for the Web Push subscription router and service."""

import ipaddress
from unittest.mock import patch

# Push endpoint hosts must resolve to public IPs (#1316); stub DNS so the
# suite stays hermetic.
_PUBLIC_IPS = {ipaddress.ip_address("93.184.216.34")}


def test_vapid_public_key_unconfigured(client):
    resp = client.get("/push/vapid-public-key")
    assert resp.status_code == 200
    assert resp.json()["publicKey"] is None


def test_subscribe_requires_keys(client):
    resp = client.post(
        "/push/subscribe",
        json={
            "endpoint": "https://fcm.example.com/token",
            "keys": {"p256dh": "foo"},
        },
    )
    assert resp.status_code == 422


def test_subscribe_and_unsubscribe(client):
    with patch("services.url_security._resolve_ips", return_value=_PUBLIC_IPS):
        resp = client.post(
            "/push/subscribe",
            json={
                "endpoint": "https://fcm.example.com/token",
                "keys": {
                    "p256dh": "p256dh-key",
                    "auth": "auth-key",
                },
            },
        )
    assert resp.status_code == 200

    resp = client.post("/push/unsubscribe")
    assert resp.status_code == 200


def test_send_test_push_without_subscriptions(client):
    with patch("services.push_service.webpush") as mock_webpush:
        resp = client.post(
            "/push/test",
            json={
                "title": "Hello",
                "body": "World",
            },
        )
        assert resp.status_code == 200
        mock_webpush.assert_not_called()
