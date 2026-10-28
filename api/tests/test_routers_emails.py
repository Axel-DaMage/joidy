import pytest
from fastapi.testclient import TestClient


def _payload(gmail_id: str = "abc123", account: str = "me@gmail.com", **overrides) -> dict:
    base = {
        "account": account,
        "gmail_id": gmail_id,
        "thread_id": f"t-{gmail_id}",
        "subject": "Quedamos hoy?",
        "sender": "Ana <ana@example.com>",
        "snippet": "Hola, te parece a las 6?",
        "body_text": "Hola, te parece a las 6?",
        "received_at": "2026-10-25T18:30:00+00:00",
        "unread": True,
        "important": True,
        "importance_reason": "sender allowlist",
        "labels": ["INBOX"],
    }
    base.update(overrides)
    return base


def test_upsert_email_created_and_updated(client: TestClient):
    first = client.post("/emails/", json=_payload())
    assert first.status_code == 201
    body = first.json()
    assert body["account"] == "me@gmail.com"
    assert body["gmail_id"] == "abc123"
    assert body["important"] is True
    assert body["created"] is True

    # Same (account, gmail_id) again → no duplicate, updated fields.
    second = client.post("/emails/", json=_payload(subject="Cambio de plan", snippet="Nuevo snippet"))
    assert second.status_code == 201
    updated = second.json()
    assert updated["id"] == body["id"]
    assert updated["created"] is False
    assert updated["subject"] == "Cambio de plan"

    listing = client.get("/emails/").json()
    assert listing["total"] == 1
    assert len(listing["items"]) == 1


def test_manual_read_wins_over_resync(client: TestClient):
    """Manual unread/read state set from the UI must not be reverted by the
    next 15-min sync pushing unread=True again (Gmail never learns about
    actions taken in joidy)."""
    email_id = client.post("/emails/", json=_payload()).json()["id"]

    client.patch(f"/emails/{email_id}", json={"unread": False})
    resync = client.post(
        "/emails/", json=_payload(gmail_id="abc123", unread=True, subject="Factura octubre")
    )
    assert resync.status_code == 201
    assert resync.json()["id"] == email_id
    assert resync.json()["created"] is False
    assert resync.json()["unread"] is False

    # Conversely: important=True from the sync IS allowed to upgrade a row,
    # but a later important=False push must not demote a manually starred one.
    client.patch(f"/emails/{email_id}", json={"important": True})
    demote = client.post("/emails/", json=_payload(gmail_id="abc123", important=False))
    assert demote.json()["important"] is True


def test_list_filters(client: TestClient):
    client.post("/emails/", json=_payload("e1", important=True, unread=True))
    client.post("/emails/", json=_payload("e2", important=False, unread=False))
    client.post("/emails/", json=_payload("e3", account="work@gmail.com", important=False))

    all_items = client.get("/emails/")
    assert all_items.status_code == 200
    assert all_items.json()["total"] == 3

    important_only = client.get("/emails/", params={"important": "true"})
    assert {m["gmail_id"] for m in important_only.json()["items"]} == {"e1"}

    unread_only = client.get("/emails/", params={"unread": "true"})
    assert {m["gmail_id"] for m in unread_only.json()["items"]} == {"e1", "e3"}

    by_account = client.get("/emails/", params={"account": "work@gmail.com"})
    assert [m["gmail_id"] for m in by_account.json()["items"]] == ["e3"]
    assert by_account.json()["total"] == 1

    search = client.get("/emails/", params={"q": "Ana"})
    assert {m["gmail_id"] for m in search.json()["items"]} >= {"e1"}
    assert search.json()["total"] >= 1


def test_patch_email_state(client: TestClient):
    email_id = client.post("/emails/", json=_payload()).json()["id"]

    marked = client.patch(f"/emails/{email_id}", json={"unread": False, "important": False})
    assert marked.status_code == 200
    assert marked.json()["unread"] is False
    assert marked.json()["important"] is False

    unknown = client.patch("/emails/999999", json={"unread": True})
    assert unknown.status_code == 404


def test_delete_email(client: TestClient):
    email_id = client.post("/emails/", json=_payload()).json()["id"]

    assert client.delete(f"/emails/{email_id}").status_code == 204
    assert client.get("/emails/").json()["total"] == 0
    assert client.delete(f"/emails/{email_id}").status_code == 404


def test_accounts_view(client: TestClient):
    client.post("/emails/", json=_payload("a1", account="me@gmail.com"))
    client.post("/emails/", json=_payload("a2", account="me@gmail.com", unread=False, important=False))
    client.post("/emails/", json=_payload("a3", account="work@gmail.com"))

    accounts = client.get("/emails/accounts")
    assert accounts.status_code == 200
    by_name = {a["account"]: a for a in accounts.json()}
    assert by_name["me@gmail.com"]["total"] == 2
    assert by_name["me@gmail.com"]["unread"] == 1
    assert by_name["me@gmail.com"]["important"] == 1
    assert by_name["work@gmail.com"]["total"] == 1


def test_invalid_payload_rejected(client: TestClient):
    missing_gmail_id = client.post("/emails/", json={"account": "me@gmail.com"})
    assert missing_gmail_id.status_code == 422

    bad_date = client.post("/emails/", json=_payload(received_at="not-a-date"))
    assert bad_date.status_code == 422

    empty_gmail_id = client.post("/emails/", json=_payload(gmail_id="   "))
    assert empty_gmail_id.status_code == 422


def test_push_needs_auth(client_no_auth: TestClient):
    assert client_no_auth.post("/emails/", json=_payload()).status_code == 401
