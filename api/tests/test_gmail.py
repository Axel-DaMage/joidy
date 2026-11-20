"""Tests for the Gmail router (#42) — Gmail API proxy.

HTTP to Google is mocked at ``httpx.AsyncClient`` level (same pattern as
test_contacts.py): ``get`` covers reads (list/get/attachment/history),
``request`` covers mutations (modify/send/watch/stop). Tokens are stored
through ``google_token_service.store_tokens`` so scope checks and the
auto-refresh path run for real. No network, SQLite+PG safe.
"""

import base64
import json
from email import message_from_bytes
from email import policy as email_policy
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from services import gmail_service as gms
from services import google_token_service as gts

GMAIL_READONLY_SCOPE = (
    "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/calendar.readonly"
)
GMAIL_MODIFY_SCOPE = (
    "https://www.googleapis.com/auth/gmail.readonly "
    "https://www.googleapis.com/auth/gmail.modify "
    "https://www.googleapis.com/auth/gmail.send "
    "https://www.googleapis.com/auth/calendar.readonly"
)
CALENDAR_ONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"

GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"


def _b64url(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).rstrip(b"=").decode()


def _fake_response(payload=None, status: int = 200):
    """Success-path mock: json() returns payload; empty payload → empty body."""
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload if payload is not None else {}
    resp.content = b"{}" if payload is not None else b""
    resp.raise_for_status.return_value = None
    return resp


def _http_error(status: int, body: dict | None = None) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", f"{GMAIL_API}/messages")
    response = httpx.Response(status, request=request, json=body or {})
    return httpx.HTTPStatusError(f"HTTP {status}", request=request, response=response)


def _error_response(status: int, body: dict | None = None):
    resp = _fake_response(status=status)
    resp.raise_for_status.side_effect = _http_error(status, body)
    return resp


def _connect(db_session, monkeypatch, scope: str = GMAIL_MODIFY_SCOPE) -> None:
    """Store a connected Google token with the given granted scope set."""
    monkeypatch.setattr("config.settings.secret_key", "test-secret")
    gts.store_tokens(
        db_session,
        access_token="ACCESS_TOKEN",
        refresh_token="REFRESH_TOKEN",
        expires_in=3600,
        token_type="Bearer",
        scope=scope,
    )


FULL_MESSAGE = {
    "id": "msg1",
    "threadId": "thread1",
    "labelIds": ["INBOX", "UNREAD"],
    "snippet": "Hello there",
    "internalDate": "1704103200000",
    "sizeEstimate": 4321,
    "historyId": "777",
    "payload": {
        "mimeType": "multipart/mixed",
        "headers": [
            {"name": "From", "value": "Alice <alice@example.com>"},
            {"name": "To", "value": "me@example.com"},
            {"name": "Cc", "value": "bob@example.com"},
            {"name": "Subject", "value": "Quarterly report"},
            {"name": "Date", "value": "Mon, 1 Jan 2024 10:00:00 +0000"},
            {"name": "Message-ID", "value": "<m1@example.com>"},
            {"name": "X-Custom", "value": "not-exposed"},
        ],
        "body": {"size": 0},
        "parts": [
            {
                "mimeType": "multipart/alternative",
                "headers": [],
                "body": {"size": 0},
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "headers": [{"name": "Content-Type", "value": "text/plain; charset=UTF-8"}],
                        "body": {"size": 5, "data": _b64url("plain")},
                    },
                    {
                        "mimeType": "text/html",
                        "headers": [],
                        "body": {"size": 12, "data": _b64url("<b>html</b>!")},
                    },
                ],
            },
            {
                "mimeType": "application/pdf",
                "filename": "report.pdf",
                "partId": "1",
                "headers": [],
                "body": {"attachmentId": "ATT1", "size": 2048},
            },
        ],
    },
}

HISTORY_RESPONSE = {
    "historyId": "900",
    "nextPageToken": "hpt",
    "history": [
        {
            "id": "888",
            "messagesAdded": [{"message": {"id": "m9", "threadId": "t9", "labelIds": ["INBOX"]}}],
            "messagesDeleted": [{"message": {"id": "m8", "threadId": "t8"}}],
            "labelsAdded": [{"message": {"id": "m7"}, "labelIds": ["STARRED"]}],
            "labelsRemoved": [],
        }
    ],
}


# ---------------------------------------------------------------------------
# Status & auth
# ---------------------------------------------------------------------------


def test_status_not_connected(client):
    resp = client.get("/integrations/gmail/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is False
    assert data["gmail_read"] is None
    assert data["gmail_modify"] is None
    assert data["gmail_send"] is None
    assert data["watch"]["configured"] is False
    assert data["watch"]["state"] is None


def test_status_connected_readonly(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch, GMAIL_READONLY_SCOPE)
    resp = client.get("/integrations/gmail/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is True
    assert data["gmail_read"] is True
    assert data["gmail_modify"] is False
    assert data["gmail_send"] is False


def test_status_connected_full(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch, GMAIL_MODIFY_SCOPE)
    resp = client.get("/integrations/gmail/status")
    data = resp.json()
    assert data["gmail_read"] is True
    assert data["gmail_modify"] is True
    assert data["gmail_send"] is True


def test_endpoints_require_auth(client_no_auth):
    assert client_no_auth.get("/integrations/gmail/status").status_code == 401
    assert client_no_auth.get("/integrations/gmail/messages").status_code == 401
    assert client_no_auth.get("/integrations/gmail/messages/m1").status_code == 401
    assert client_no_auth.post("/integrations/gmail/messages/send", json={}).status_code == 401
    assert client_no_auth.post("/integrations/gmail/messages/m1/archive").status_code == 401
    assert client_no_auth.get("/integrations/gmail/history?start_history_id=1").status_code == 401
    assert client_no_auth.post("/integrations/gmail/watch").status_code == 401
    assert client_no_auth.delete("/integrations/gmail/watch").status_code == 401


def test_list_without_connection_401(client):
    resp = client.get("/integrations/gmail/messages")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# List messages
# ---------------------------------------------------------------------------


def test_list_messages(client, db_session, monkeypatch):
    """Page items are hydrated with real summary fields via format=metadata
    gets — the bare id/threadId stubs from messages.list never reach the
    client (#1458)."""
    _connect(db_session, monkeypatch)
    payload = {
        "messages": [
            {"id": "m1", "threadId": "t1"},
            {"id": "m2", "threadId": "t2"},
        ],
        "nextPageToken": "page-2",
        "resultSizeEstimate": 42,
    }
    meta_m1 = {
        "id": "m1",
        "threadId": "t1",
        "labelIds": ["INBOX"],
        "snippet": "hi",
        "internalDate": "1704103200000",
        "historyId": "777",
        "sizeEstimate": 4321,
        "payload": {"headers": [{"name": "Subject", "value": "s"}]},
    }
    meta_m2 = {"id": "m2", "threadId": "t2"}
    responses = [_fake_response(payload), _fake_response(meta_m1), _fake_response(meta_m2)]
    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=responses)) as mock_get:
        resp = client.get(
            "/integrations/gmail/messages?q=is:unread&max_results=10&page_token=tok1&label_ids=INBOX,Label_9"
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["next_page_token"] == "page-2"
    assert data["result_size_estimate"] == 42
    assert len(data["messages"]) == 2
    first = data["messages"][0]
    assert first["id"] == "m1"
    assert first["thread_id"] == "t1"
    assert first["label_ids"] == ["INBOX"]
    assert first["snippet"] == "hi"
    assert first["internal_date"] == "2024-01-01T10:00:00+00:00"
    assert first["history_id"] == "777"
    assert first["size_estimate"] == 4321
    assert data["messages"][1]["internal_date"] is None

    call = mock_get.call_args_list[0]
    assert call.args[0] == f"{GMAIL_API}/messages"
    params = call.kwargs["params"]
    assert params["q"] == "is:unread"
    assert params["maxResults"] == 10
    assert params["pageToken"] == "tok1"
    assert params["labelIds"] == ["INBOX", "Label_9"]
    assert call.kwargs["headers"]["Authorization"] == "Bearer ACCESS_TOKEN"


def test_list_messages_hydration_uses_metadata_format(client, db_session, monkeypatch):
    """Hydration gets run format=metadata + metadataHeaders — never format=full
    (whole MIME bodies at N× the payload for no summary gain)."""
    _connect(db_session, monkeypatch)
    payload = {"messages": [{"id": "m1", "threadId": "t1"}]}
    responses = [_fake_response(payload), _fake_response({"id": "m1", "snippet": "s"})]
    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=responses)) as mock_get:
        resp = client.get("/integrations/gmail/messages")

    assert resp.status_code == 200
    get_call = mock_get.call_args_list[1]
    assert get_call.args[0] == f"{GMAIL_API}/messages/m1"
    params = get_call.kwargs["params"]
    assert params["format"] == "metadata"
    assert set(params["metadataHeaders"]) == {"Subject", "From", "Date"}


def test_list_messages_hydration_failure_degrades_to_stub(client, db_session, monkeypatch):
    """A single failing messages.get must not fail the page — that item keeps
    its bare id/threadId stub while siblings hydrate normally (#1458)."""
    _connect(db_session, monkeypatch)
    payload = {
        "messages": [
            {"id": "m1", "threadId": "t1"},
            {"id": "m2", "threadId": "t2"},
        ]
    }
    meta_m1 = {
        "id": "m1",
        "threadId": "t1",
        "labelIds": ["INBOX"],
        "snippet": "ok",
        "internalDate": "1704103200000",
    }

    def fake_get(url, **kwargs):
        if url.endswith("/messages"):
            return _fake_response(payload)
        if url.endswith("/messages/m2"):
            return _error_response(404)
        return _fake_response(meta_m1)

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=fake_get)):
        resp = client.get("/integrations/gmail/messages")

    assert resp.status_code == 200
    messages = {m["id"]: m for m in resp.json()["messages"]}
    assert messages["m1"]["snippet"] == "ok"
    assert messages["m1"]["label_ids"] == ["INBOX"]
    assert messages["m2"]["thread_id"] == "t2"
    assert messages["m2"]["snippet"] is None
    assert messages["m2"]["label_ids"] == []


def test_list_messages_hydration_timeout_degrades_to_stub(client, db_session, monkeypatch):
    """A hanging/slow messages.get surfaces as an httpx error — same stub
    degradation as a status error, never a page-level 500."""
    _connect(db_session, monkeypatch)
    payload = {"messages": [{"id": "m1", "threadId": "t1"}]}

    def fake_get(url, **kwargs):
        if url.endswith("/messages"):
            return _fake_response(payload)
        raise httpx.TimeoutException("slow", request=httpx.Request("GET", url))

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=fake_get)):
        resp = client.get("/integrations/gmail/messages")

    assert resp.status_code == 200
    msg = resp.json()["messages"][0]
    assert msg["id"] == "m1"
    assert msg["thread_id"] == "t1"
    assert msg["snippet"] is None


def test_list_messages_since_epoch(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_fake_response({"messages": []}))) as mock_get:
        resp = client.get("/integrations/gmail/messages?since=1700000000")
    assert resp.status_code == 200
    assert mock_get.call_args_list[0].kwargs["params"]["q"] == "after:1700000000"


def test_list_messages_since_iso(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_fake_response({"messages": []}))) as mock_get:
        resp = client.get("/integrations/gmail/messages?since=2024-01-01T00:00:00Z")
    assert resp.status_code == 200
    assert mock_get.call_args_list[0].kwargs["params"]["q"] == "after:1704067200"


def test_list_messages_since_combines_with_q(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_fake_response({"messages": []}))) as mock_get:
        resp = client.get("/integrations/gmail/messages?q=in:inbox&since=1700000000")
    assert resp.status_code == 200
    assert mock_get.call_args_list[0].kwargs["params"]["q"] == "in:inbox after:1700000000"


def test_list_messages_invalid_since(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    resp = client.get("/integrations/gmail/messages?since=not-a-date")
    assert resp.status_code == 400


def test_list_messages_invalid_label(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    resp = client.get("/integrations/gmail/messages?label_ids=INBOX;DROP")
    assert resp.status_code == 400


def test_list_messages_explicit_token(client):
    """The ``X-Google-Token`` header bypasses the stored-token lookup — the
    legacy ``?token=`` query param was removed (#1461)."""
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_fake_response({"messages": []}))) as mock_get:
        resp = client.get("/integrations/gmail/messages", headers={"X-Google-Token": "xyz"})
    assert resp.status_code == 200
    assert mock_get.call_args_list[0].kwargs["headers"]["Authorization"] == "Bearer xyz"


def test_list_messages_query_token_ignored(client):
    """``?token=`` must NOT be honored — credentials in URLs leak into logs.
    With no stored connection the request falls through to the stored-token
    path and answers 401 (#1461)."""
    with patch("httpx.AsyncClient.get", new=AsyncMock()) as mock_get:
        resp = client.get("/integrations/gmail/messages?token=xyz")
    assert resp.status_code == 401
    mock_get.assert_not_called()


def test_list_messages_no_read_scope_rejected(client, db_session, monkeypatch):
    """A provably under-scoped token fails before any Google call."""
    _connect(db_session, monkeypatch, CALENDAR_ONLY_SCOPE)
    with patch("httpx.AsyncClient.get", new=AsyncMock()) as mock_get:
        resp = client.get("/integrations/gmail/messages")
    assert resp.status_code == 403
    mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# Get message
# ---------------------------------------------------------------------------


def test_get_message_detail(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_fake_response(FULL_MESSAGE))) as mock_get:
        resp = client.get("/integrations/gmail/messages/msg1")

    assert resp.status_code == 200
    msg = resp.json()
    assert msg["id"] == "msg1"
    assert msg["thread_id"] == "thread1"
    assert msg["internal_date"] == "2024-01-01T10:00:00+00:00"
    assert msg["headers"]["from"] == "Alice <alice@example.com>"
    assert msg["headers"]["to"] == "me@example.com"
    assert msg["headers"]["subject"] == "Quarterly report"
    # Non-standard headers are not forwarded to the client contract.
    assert "x-custom" not in msg["headers"]
    assert msg["body_text"] == "plain"
    assert msg["body_html"] == "<b>html</b>!"
    assert msg["body_truncated"] is False
    assert msg["attachments"] == [
        {
            "attachment_id": "ATT1",
            "filename": "report.pdf",
            "mime_type": "application/pdf",
            "size": 2048,
            "part_id": "1",
        }
    ]

    call = mock_get.call_args_list[0]
    assert call.args[0] == f"{GMAIL_API}/messages/msg1"
    assert call.kwargs["params"] == {"format": "full"}


def test_get_message_simple_body(client, db_session, monkeypatch):
    """Non-multipart messages carry body.data directly on the payload."""
    _connect(db_session, monkeypatch)
    payload = {
        "id": "m2",
        "threadId": "t2",
        "labelIds": ["SENT"],
        "snippet": "s",
        "payload": {
            "mimeType": "text/plain",
            "headers": [{"name": "Subject", "value": "Hi"}],
            "body": {"size": 11, "data": _b64url("hello world")},
        },
    }
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_fake_response(payload))):
        resp = client.get("/integrations/gmail/messages/m2")
    assert resp.status_code == 200
    assert resp.json()["body_text"] == "hello world"
    assert resp.json()["body_html"] is None
    assert resp.json()["attachments"] == []


def test_get_message_not_found(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_error_response(404))):
        resp = client.get("/integrations/gmail/messages/missing")
    assert resp.status_code == 404


def test_get_message_invalid_id(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    assert client.get("/integrations/gmail/messages/bad%2Fid").status_code in (400, 404, 422)
    assert client.get("/integrations/gmail/messages/..").status_code in (400, 404, 422)


# ---------------------------------------------------------------------------
# Attachment download
# ---------------------------------------------------------------------------


def test_get_attachment(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    raw = _b64url("PDF-BYTES")
    payload = {"size": 9, "data": raw}
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_fake_response(payload))) as mock_get:
        resp = client.get("/integrations/gmail/messages/msg1/attachments/ATT1")

    assert resp.status_code == 200
    data = resp.json()
    assert data["attachment_id"] == "ATT1"
    assert data["size"] == 9
    # Standard base64 (not urlsafe) for JSON transport.
    assert base64.b64decode(data["data_base64"]) == b"PDF-BYTES"

    call = mock_get.call_args_list[0]
    assert call.args[0] == f"{GMAIL_API}/messages/msg1/attachments/ATT1"


def test_get_attachment_too_large(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    monkeypatch.setattr(gms, "MAX_IN_ATTACHMENT_B64_CHARS", 8)
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_fake_response({"data": "QUJDREVGR0g="}))):
        resp = client.get("/integrations/gmail/messages/m1/attachments/A1")
    assert resp.status_code == 413


def test_get_attachment_invalid_ids(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    assert client.get("/integrations/gmail/messages/bad%2Fid/attachments/A1").status_code in (400, 404, 422)
    assert client.get("/integrations/gmail/messages/m1/attachments/bad%2Fid").status_code in (400, 404, 422)


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------


def _decode_sent_raw(call) -> bytes:
    """Extract + decode the RFC822 payload from a messages.send mock call."""
    raw = call.kwargs["json"]["raw"]
    padded = raw + "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(padded)


def test_send_message(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    sent = {"id": "sent1", "threadId": "thread-s", "labelIds": ["SENT"]}
    with patch("httpx.AsyncClient.request", new=AsyncMock(return_value=_fake_response(sent))) as mock_req:
        resp = client.post(
            "/integrations/gmail/messages/send",
            json={"to": "bob@example.com", "subject": "Hola", "body": "Qué tal"},
        )

    assert resp.status_code == 200
    assert resp.json() == {"id": "sent1", "thread_id": "thread-s", "label_ids": ["SENT"]}

    call = mock_req.call_args_list[0]
    assert call.args[0] == "POST"
    assert call.args[1] == f"{GMAIL_API}/messages/send"
    mime = message_from_bytes(_decode_sent_raw(call), policy=email_policy.default)
    assert mime["To"] == "bob@example.com"
    assert mime["Subject"] == "Hola"
    assert mime.get_content_type() == "text/plain"
    assert "Qué tal" in mime.get_content()


def test_send_message_full_payload(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.request", new=AsyncMock(return_value=_fake_response({"id": "s1"}))) as mock_req:
        resp = client.post(
            "/integrations/gmail/messages/send",
            json={
                "to": "a@example.com, Bob <bob@example.com>",
                "cc": "carol@example.com",
                "bcc": "dan@example.com",
                "subject": "Report",
                "body": "plain version",
                "body_html": "<p>html version</p>",
                "attachments": [
                    {
                        "filename": "notes.txt",
                        "content_type": "text/plain",
                        "data_base64": base64.b64encode(b"attachment body").decode(),
                    }
                ],
            },
        )
    assert resp.status_code == 200
    mime = message_from_bytes(_decode_sent_raw(mock_req.call_args_list[0]), policy=email_policy.default)
    assert mime.get_content_type() == "multipart/mixed"
    content_types = [part.get_content_type() for part in mime.walk()]
    assert "text/plain" in content_types and "text/html" in content_types
    filenames = [part.get_filename() for part in mime.walk() if part.get_filename()]
    assert filenames == ["notes.txt"]
    # Bcc header is set on the wire (Gmail strips it from recipients' copies).
    assert mime["Bcc"] == "dan@example.com"
    assert mime["Cc"] == "carol@example.com"


def test_send_message_crlf_injection_sanitized(client, db_session, monkeypatch):
    """CRLF in subject/recipients must collapse — no header injection."""
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.request", new=AsyncMock(return_value=_fake_response({"id": "s1"}))) as mock_req:
        resp = client.post(
            "/integrations/gmail/messages/send",
            json={
                "to": "victim@example.com",
                "subject": "Hi\r\nBcc: attacker@evil.com",
                "body": "x",
            },
        )
    assert resp.status_code == 200
    mime = message_from_bytes(_decode_sent_raw(mock_req.call_args_list[0]), policy=email_policy.default)
    assert mime["Subject"] == "Hi Bcc: attacker@evil.com"
    assert mime["Bcc"] is None


def test_send_message_display_name_recipient(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.request", new=AsyncMock(return_value=_fake_response({"id": "s1"}))) as mock_req:
        resp = client.post(
            "/integrations/gmail/messages/send",
            json={"to": "Bob Smith <bob@example.com>", "body": "hi"},
        )
    assert resp.status_code == 200
    mime = message_from_bytes(_decode_sent_raw(mock_req.call_args_list[0]), policy=email_policy.default)
    assert "bob@example.com" in str(mime["To"])


def test_send_message_no_recipients_400(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    resp = client.post("/integrations/gmail/messages/send", json={"subject": "x", "body": "y"})
    assert resp.status_code == 400


def test_send_message_empty_body_400(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    resp = client.post("/integrations/gmail/messages/send", json={"to": "a@b.com", "body": "   "})
    assert resp.status_code == 400


def test_send_message_invalid_recipient_400(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    resp = client.post("/integrations/gmail/messages/send", json={"to": "not-an-email", "body": "x"})
    assert resp.status_code == 400


def test_send_message_bad_attachment_b64_400(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    resp = client.post(
        "/integrations/gmail/messages/send",
        json={
            "to": "a@b.com",
            "body": "x",
            "attachments": [{"filename": "x.bin", "data_base64": "!!!not-base64!!!"}],
        },
    )
    assert resp.status_code == 400


def test_send_message_attachment_crlf_content_type_sanitized(client, db_session, monkeypatch):
    """CRLF/garbage in attachment content_type collapses to octet-stream — no 500, no malformed MIME."""
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.request", new=AsyncMock(return_value=_fake_response({"id": "s1"}))) as mock_req:
        resp = client.post(
            "/integrations/gmail/messages/send",
            json={
                "to": "a@b.com",
                "body": "x",
                "attachments": [
                    {
                        "filename": "x.txt",
                        "content_type": "text/plain\r\nBcc: attacker@evil.com",
                        "data_base64": "aGk=",
                    }
                ],
            },
        )
    assert resp.status_code == 200
    mime = message_from_bytes(_decode_sent_raw(mock_req.call_args_list[0]), policy=email_policy.default)
    assert any(part.get_content_type() == "application/octet-stream" for part in mime.walk())


def test_send_message_attachment_odd_content_type_falls_back(client, db_session, monkeypatch):
    """A content_type without '/' degrades to octet-stream instead of failing."""
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.request", new=AsyncMock(return_value=_fake_response({"id": "s1"}))) as mock_req:
        resp = client.post(
            "/integrations/gmail/messages/send",
            json={
                "to": "a@b.com",
                "body": "x",
                "attachments": [{"filename": "x.bin", "content_type": "weirdtype", "data_base64": "aGk="}],
            },
        )
    assert resp.status_code == 200
    mime = message_from_bytes(_decode_sent_raw(mock_req.call_args_list[0]), policy=email_policy.default)
    assert any(part.get_content_type() == "application/octet-stream" for part in mime.walk())


def test_send_message_readonly_scope_rejected(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch, GMAIL_READONLY_SCOPE)
    with patch("httpx.AsyncClient.request", new=AsyncMock()) as mock_req:
        resp = client.post("/integrations/gmail/messages/send", json={"to": "a@b.com", "body": "x"})
    assert resp.status_code == 403
    mock_req.assert_not_called()


def test_send_message_modify_scope_allows_send(client, db_session, monkeypatch):
    """gmail.modify implies send capability (Google scope hierarchy)."""
    _connect(db_session, monkeypatch, GMAIL_MODIFY_SCOPE)
    with patch("httpx.AsyncClient.request", new=AsyncMock(return_value=_fake_response({"id": "s1"}))):
        resp = client.post("/integrations/gmail/messages/send", json={"to": "a@b.com", "body": "x"})
    assert resp.status_code == 200


def test_send_message_no_connection(client):
    resp = client.post("/integrations/gmail/messages/send", json={"to": "a@b.com", "body": "x"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Label actions — archive / trash / untrash / read / unread
# ---------------------------------------------------------------------------


def _assert_modify_call(mock_req, message_id: str, add: list, remove: list):
    call = mock_req.call_args_list[0]
    assert call.args[0] == "POST"
    assert call.args[1] == f"{GMAIL_API}/messages/{message_id}/modify"
    assert call.kwargs["json"] == {"addLabelIds": add, "removeLabelIds": remove}


def test_archive_message(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    updated = {"id": "m1", "threadId": "t1", "labelIds": ["UNREAD"]}
    with patch("httpx.AsyncClient.request", new=AsyncMock(return_value=_fake_response(updated))) as mock_req:
        resp = client.post("/integrations/gmail/messages/m1/archive")
    assert resp.status_code == 200
    assert resp.json()["label_ids"] == ["UNREAD"]
    _assert_modify_call(mock_req, "m1", [], ["INBOX"])


def test_trash_message(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.request", new=AsyncMock(return_value=_fake_response({"id": "m1"}))) as mock_req:
        resp = client.post("/integrations/gmail/messages/m1/trash")
    assert resp.status_code == 200
    _assert_modify_call(mock_req, "m1", ["TRASH"], ["INBOX"])


def test_untrash_message(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.request", new=AsyncMock(return_value=_fake_response({"id": "m1"}))) as mock_req:
        resp = client.post("/integrations/gmail/messages/m1/untrash")
    assert resp.status_code == 200
    _assert_modify_call(mock_req, "m1", ["INBOX"], ["TRASH"])


def test_mark_read_message(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.request", new=AsyncMock(return_value=_fake_response({"id": "m1"}))) as mock_req:
        resp = client.post("/integrations/gmail/messages/m1/read")
    assert resp.status_code == 200
    _assert_modify_call(mock_req, "m1", [], ["UNREAD"])


def test_mark_unread_message(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.request", new=AsyncMock(return_value=_fake_response({"id": "m1"}))) as mock_req:
        resp = client.post("/integrations/gmail/messages/m1/unread")
    assert resp.status_code == 200
    _assert_modify_call(mock_req, "m1", ["UNREAD"], [])


def test_label_action_readonly_scope_rejected(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch, GMAIL_READONLY_SCOPE)
    with patch("httpx.AsyncClient.request", new=AsyncMock()) as mock_req:
        resp = client.post("/integrations/gmail/messages/m1/archive")
    assert resp.status_code == 403
    mock_req.assert_not_called()


def test_label_action_invalid_id(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    resp = client.post("/integrations/gmail/messages/bad%2Fid/trash")
    assert resp.status_code in (400, 404, 422)


# ---------------------------------------------------------------------------
# users.watch — push registration + history polling
# ---------------------------------------------------------------------------


def test_watch_not_configured(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    monkeypatch.setattr("config.settings.google_gmail_pubsub_topic", "")
    resp = client.post("/integrations/gmail/watch")
    assert resp.status_code == 503


def test_watch_status_not_configured(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    monkeypatch.setattr("config.settings.google_gmail_pubsub_topic", "")
    resp = client.get("/integrations/gmail/watch")
    assert resp.status_code == 200
    assert resp.json() == {"configured": False, "state": None}


def test_watch_register_and_status(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    monkeypatch.setattr("config.settings.google_gmail_pubsub_topic", "projects/p/topics/joidy-gmail")
    watch_resp = {"historyId": "12345", "expiration": "1893456000000"}
    with patch("httpx.AsyncClient.request", new=AsyncMock(return_value=_fake_response(watch_resp))) as mock_req:
        resp = client.post("/integrations/gmail/watch?label_ids=INBOX")

    assert resp.status_code == 200
    data = resp.json()
    assert data["topic_name"] == "projects/p/topics/joidy-gmail"
    assert data["history_id"] == "12345"
    assert data["expiration"] == "2030-01-01T00:00:00+00:00"

    call = mock_req.call_args_list[0]
    assert call.args[0] == "POST"
    assert call.args[1] == f"{GMAIL_API}/watch"
    assert call.kwargs["json"] == {"topicName": "projects/p/topics/joidy-gmail", "labelIds": ["INBOX"]}

    # State persisted → GET /watch reports it.
    status = client.get("/integrations/gmail/watch")
    assert status.json()["configured"] is True
    assert status.json()["state"]["history_id"] == "12345"

    # And /status surfaces it too.
    full = client.get("/integrations/gmail/status")
    assert full.json()["watch"]["state"]["topic_name"] == "projects/p/topics/joidy-gmail"


def test_watch_stop_clears_state(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    monkeypatch.setattr("config.settings.google_gmail_pubsub_topic", "projects/p/topics/t")
    with patch("httpx.AsyncClient.request", new=AsyncMock(return_value=_fake_response({"historyId": "1"}))):
        assert client.post("/integrations/gmail/watch").status_code == 200
    with patch("httpx.AsyncClient.request", new=AsyncMock(return_value=_fake_response(None))) as mock_req:
        resp = client.delete("/integrations/gmail/watch")
    assert resp.status_code == 200
    assert resp.json() == {"status": "stopped"}
    assert mock_req.call_args_list[0].args[1] == f"{GMAIL_API}/stop"
    assert client.get("/integrations/gmail/watch").json()["state"] is None


def test_history(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_fake_response(HISTORY_RESPONSE))) as mock_get:
        resp = client.get(
            "/integrations/gmail/history?start_history_id=800&page_token=pt1&max_results=50&label_id=INBOX"
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["history_id"] == "900"
    assert data["next_page_token"] == "hpt"
    assert len(data["records"]) == 1
    rec = data["records"][0]
    assert rec["id"] == "888"
    assert rec["messages_added"] == [{"id": "m9", "thread_id": "t9", "label_ids": ["INBOX"]}]
    assert rec["messages_deleted"] == [{"id": "m8", "thread_id": "t8", "label_ids": []}]
    assert rec["labels_added"] == [{"message_id": "m7", "label_ids": ["STARRED"]}]
    assert rec["labels_removed"] == []

    call = mock_get.call_args_list[0]
    assert call.args[0] == f"{GMAIL_API}/history"
    params = call.kwargs["params"]
    assert params["startHistoryId"] == "800"
    assert params["pageToken"] == "pt1"
    assert params["maxResults"] == 50
    assert params["labelId"] == "INBOX"


def test_history_requires_start_id(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    resp = client.get("/integrations/gmail/history")
    assert resp.status_code == 422


def test_history_invalid_id(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    resp = client.get("/integrations/gmail/history?start_history_id=abc!")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


def test_google_401_maps_to_reconnect(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_error_response(401))):
        resp = client.get("/integrations/gmail/messages")
    assert resp.status_code == 401
    assert "conecta" in resp.json()["detail"]


def test_insufficient_permissions_maps_to_403(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    body = {"error": {"errors": [{"reason": "insufficientPermissions", "message": "Insufficient Permission"}]}}
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_error_response(403, body))):
        resp = client.get("/integrations/gmail/messages/m1")
    assert resp.status_code == 403
    assert "permiso" in resp.json()["detail"]


def test_google_404_maps(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_error_response(404))):
        resp = client.get("/integrations/gmail/messages/m1")
    assert resp.status_code == 404


def test_google_429_maps(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_error_response(429))):
        resp = client.get("/integrations/gmail/messages")
    assert resp.status_code == 429


def test_google_500_maps_to_502(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_error_response(500))):
        resp = client.get("/integrations/gmail/messages")
    assert resp.status_code == 502
    assert resp.json()["detail"] == "Gmail API error"


def test_google_400_maps(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_error_response(400))):
        resp = client.get("/integrations/gmail/messages")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Pure unit tests — normalization, RFC822, capabilities
# ---------------------------------------------------------------------------


def test_normalize_message_minimal():
    out = gms.normalize_message({"id": "m1", "payload": {"headers": []}})
    assert out["id"] == "m1"
    assert out["thread_id"] is None
    assert out["label_ids"] == []
    assert out["body_text"] is None
    assert out["body_html"] is None
    assert out["attachments"] == []
    assert out["headers"] == {}


def test_normalize_message_skips_attachment_parts_for_bodies():
    """A part with filename+attachmentId must never be decoded as a body."""
    payload = {
        "mimeType": "multipart/mixed",
        "headers": [],
        "parts": [
            {"mimeType": "text/plain", "filename": "", "body": {"data": _b64url("real body")}},
            {
                "mimeType": "text/plain",
                "filename": "fake.txt",
                "body": {"attachmentId": "A9", "size": 10},
            },
        ],
    }
    out = gms.normalize_message({"id": "m", "payload": payload})
    assert out["body_text"] == "real body"
    assert len(out["attachments"]) == 1


def test_normalize_history_empty():
    out = gms.normalize_history({})
    assert out == {"history_id": None, "next_page_token": None, "records": []}


def test_build_rfc822_minimal():
    raw = gms.build_rfc822(to=["a@b.com"], cc=[], bcc=[], subject="", body="hello")
    mime = message_from_bytes(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)), policy=email_policy.default)
    assert mime["To"] == "a@b.com"
    assert mime["Subject"] is None
    assert "hello" in mime.get_content()


def test_parse_recipients():
    assert gms._parse_recipients("a@b.com, c@d.com", "to") == ["a@b.com", "c@d.com"]
    assert gms._parse_recipients("Bob <bob@x.com>", "to") == ["Bob <bob@x.com>"]
    assert gms._parse_recipients(None, "to") == []
    assert gms._parse_recipients("", "to") == []
    with pytest.raises(gms.GmailValidationError):
        gms._parse_recipients("bad-address", "to")
    with pytest.raises(gms.GmailValidationError):
        gms._parse_recipients("a@b.com\r\nBcc: evil@x.com", "to")


def test_since_to_epoch():
    assert gms._since_to_epoch("1700000000") == 1700000000
    assert gms._since_to_epoch("2024-01-01T00:00:00Z") == 1704067200
    assert gms._since_to_epoch("2024-01-01") == 1704067200
    with pytest.raises(gms.GmailValidationError):
        gms._since_to_epoch("garbage")


def test_capabilities_unknown_when_no_row(db_session):
    caps = gms.gmail_capabilities(db_session)
    assert caps == {"read": None, "modify": None, "send": None}


def test_require_capability_raises_on_known_missing(db_session, monkeypatch):
    _connect(db_session, monkeypatch, GMAIL_READONLY_SCOPE)
    # read is granted, modify/send provably missing
    gms.require_capability(db_session, "read")
    with pytest.raises(gms.GmailReconsentRequired):
        gms.require_capability(db_session, "modify")
    with pytest.raises(gms.GmailReconsentRequired):
        gms.require_capability(db_session, "send")


def test_validate_gmail_id():
    assert gms.validate_gmail_id("abc123_-XYZ") == "abc123_-XYZ"
    with pytest.raises(gms.GmailValidationError):
        gms.validate_gmail_id("bad/id")
    with pytest.raises(gms.GmailValidationError):
        gms.validate_gmail_id("../etc")
    with pytest.raises(gms.GmailValidationError):
        gms.validate_gmail_id("")


def test_decode_out_attachment_size_cap():
    big = base64.b64encode(b"x" * 100).decode()
    monkey_val = gms.MAX_OUT_ATTACHMENT_BYTES
    try:
        gms.MAX_OUT_ATTACHMENT_BYTES = 10
        with pytest.raises(gms.GmailValidationError):
            gms._decode_out_attachment(big, "big.bin")
    finally:
        gms.MAX_OUT_ATTACHMENT_BYTES = monkey_val


def test_json_roundtrip_no_secrets():
    """Sanity: normalized payloads never contain token material."""
    out = json.dumps(gms.normalize_message(FULL_MESSAGE))
    assert "ACCESS_TOKEN" not in out
    assert "REFRESH_TOKEN" not in out
