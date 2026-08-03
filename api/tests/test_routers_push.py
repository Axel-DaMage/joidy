"""Router tests for the push notification endpoints (#13)."""

from fastapi.testclient import TestClient
from models.push_subscription import PushSubscription


def test_subscribe_creates_subscription(client: TestClient, db_session):
    payload = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/abc",
        "keys": {"p256dh": "p256dh-value", "auth": "auth-value"},
    }
    response = client.post("/push/subscribe", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    subs = db_session.query(PushSubscription).all()
    assert len(subs) == 1
    assert subs[0].endpoint == payload["endpoint"]
    assert subs[0].p256dh == "p256dh-value"
    assert subs[0].auth == "auth-value"


def test_subscribe_replaces_existing(client: TestClient, db_session):
    db_session.add(PushSubscription(
        user_id=1,
        endpoint="https://old.example.com/send",
        p256dh="old-p256dh",
        auth="old-auth",
    ))
    db_session.commit()

    payload = {
        "endpoint": "https://new.example.com/send",
        "keys": {"p256dh": "new-p256dh", "auth": "new-auth"},
    }
    response = client.post("/push/subscribe", json=payload)
    assert response.status_code == 200

    subs = db_session.query(PushSubscription).all()
    assert len(subs) == 1
    assert subs[0].endpoint == "https://new.example.com/send"


def test_subscribe_missing_keys_rejected(client: TestClient):
    payload = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/abc",
        "keys": {"p256dh": "p256dh-value"},
    }
    response = client.post("/push/subscribe", json=payload)
    assert response.status_code == 422


def test_unsubscribe_removes_subscription(client: TestClient, db_session):
    db_session.add(PushSubscription(
        user_id=1,
        endpoint="https://example.com/send",
        p256dh="p",
        auth="a",
    ))
    db_session.commit()

    response = client.post("/push/unsubscribe")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    subs = db_session.query(PushSubscription).all()
    assert len(subs) == 0


def test_unsubscribe_when_none(client: TestClient):
    response = client.post("/push/unsubscribe")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_vapid_public_key_not_configured(client: TestClient):
    response = client.get("/push/vapid-public-key")
    # VAPID not configured → returns null instead of 503 (#549)
    assert response.status_code == 200
    assert response.json()["publicKey"] is None
