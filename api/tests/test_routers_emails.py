from fastapi.testclient import TestClient
from models.email_account import PROVIDER_N8N


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
    resync = client.post("/emails/", json=_payload(gmail_id="abc123", unread=True, subject="Factura octubre"))
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


# ---------------------------------------------------------------------------
# Multi-account ingestion (#1659) — email_accounts linkage on push + filters
# ---------------------------------------------------------------------------


def test_push_links_message_to_n8n_account(client: TestClient, db_session):
    """An n8n push get-or-creates an ``email_accounts`` row (provider n8n) and
    stamps ``account_id`` on the message — ingestion works with zero setup."""
    from models.email_account import PROVIDER_N8N, EmailAccount

    res = client.post("/emails/", json=_payload())
    assert res.status_code == 201
    account_id = res.json()["account_id"]
    assert account_id is not None

    row = db_session.query(EmailAccount).filter(EmailAccount.id == account_id).one()
    assert row.provider == PROVIDER_N8N
    assert row.email_address == "me@gmail.com"

    # A second push to the same address reuses the account row.
    res2 = client.post("/emails/", json=_payload(gmail_id="other1"))
    assert res2.json()["account_id"] == account_id


def test_push_links_to_matching_gmail_account(client: TestClient, db_session):
    """A push whose ``account`` label matches a credentialled gmail mailbox
    links to that row instead of duplicating it as n8n (#1659)."""
    from models.email_account import PROVIDER_GMAIL, EmailAccount

    gmail_row = EmailAccount(
        user_id=1,
        provider=PROVIDER_GMAIL,
        email_address="me@gmail.com",
        display_name="me@gmail.com",
        is_active=True,
    )
    db_session.add(gmail_row)
    db_session.commit()

    res = client.post("/emails/", json=_payload("g1", account="me@gmail.com"))
    assert res.json()["account_id"] == gmail_row.id


def test_account_id_filter(client: TestClient):
    first = client.post("/emails/", json=_payload("f1", account="me@gmail.com")).json()
    client.post("/emails/", json=_payload("f2", account="work@gmail.com"))

    scoped = client.get("/emails/", params={"account_id": first["account_id"]})
    assert scoped.status_code == 200
    assert [m["gmail_id"] for m in scoped.json()["items"]] == ["f1"]
    assert scoped.json()["total"] == 1


def test_accounts_view_includes_account_metadata(client: TestClient, db_session):
    """The accounts view merges ``email_accounts`` rows: pushed mail shows its
    account id/provider, and a connected mailbox with zero synced mail still
    appears for the UI switcher (#1659)."""
    from models.email_account import PROVIDER_GMAIL, EmailAccount

    db_session.add(
        EmailAccount(
            user_id=1,
            provider=PROVIDER_GMAIL,
            email_address="other@gmail.com",
            display_name="Other",
            is_active=True,
        )
    )
    db_session.commit()
    client.post("/emails/", json=_payload("a1", account="me@gmail.com"))

    accounts = client.get("/emails/accounts")
    assert accounts.status_code == 200
    by_name = {a["account"]: a for a in accounts.json()}
    assert by_name["me@gmail.com"]["provider"] == PROVIDER_N8N
    assert by_name["me@gmail.com"]["account_id"] is not None
    assert by_name["me@gmail.com"]["total"] == 1
    assert by_name["other@gmail.com"]["provider"] == PROVIDER_GMAIL
    assert by_name["other@gmail.com"]["display_name"] == "Other"
    assert by_name["other@gmail.com"]["total"] == 0
