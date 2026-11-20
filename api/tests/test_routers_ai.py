"""Tests for /ai router endpoints (#13).

The AI service runs in a separate container, so all outbound ``httpx`` calls
are mocked. These tests cover the chat, classify, usage, and daily-recap
endpoints, including graceful degradation when the AI service is unreachable.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _mock_httpx(response_json: dict) -> tuple[MagicMock, MagicMock]:
    """Build a mocked ``http_client`` async-context-manager.

    Returns the class-level mock (to be asserted on) and the instance mock so
    callers can inspect which method was called.
    """
    mock_resp = MagicMock()
    mock_resp.json.return_value = response_json
    mock_resp.raise_for_status = MagicMock()

    mock_instance = MagicMock()
    mock_instance.get = AsyncMock(return_value=mock_resp)
    mock_instance.post = AsyncMock(return_value=mock_resp)
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=None)

    mock_cls = MagicMock(return_value=mock_instance)
    return mock_cls, mock_instance


# --- GET /ai/usage -----------------------------------------------------------


def _mock_httpx_get_map(responses_by_path: dict) -> tuple[MagicMock, MagicMock]:
    """Mock ``http_client`` whose ``get`` returns a different JSON body per
    upstream path — /ai/usage now queries both /usage and /health (#1460).

    Returns (class-level mock, instance mock) like ``_mock_httpx``.
    """

    def _resp(payload):
        r = MagicMock()
        r.json.return_value = payload
        r.raise_for_status = MagicMock()
        return r

    mock_instance = MagicMock()
    mock_instance.get = AsyncMock(side_effect=lambda url, **kw: _resp(responses_by_path[url.rsplit("/", 1)[-1]]))
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=None)
    return MagicMock(return_value=mock_instance), mock_instance


@patch("routers.ai.http_client")
def test_ai_usage_returns_data(mock_client_cls, client: TestClient):
    mock_cls, mock_instance = _mock_httpx_get_map(
        {
            "usage": {"ai_enabled": True, "estimated_cost_usd": 1.23, "tokens": 5000},
            "health": {"ai_enabled": True, "status": "ok"},
        }
    )
    mock_client_cls.side_effect = mock_cls

    resp = client.get("/ai/usage")

    assert resp.status_code == 200
    data = resp.json()
    assert data["ai_enabled"] is True
    assert data["estimated_cost_usd"] == 1.23
    # #1460: health probe fields merge into the usage payload.
    assert data["ai_status"] == "ok"
    assert data["ai_status_detail"] is None
    assert mock_instance.get.await_count == 2


@patch("routers.ai.http_client")
def test_ai_usage_unreachable_returns_fallback(mock_client_cls, client: TestClient):
    """When the AI service is down the endpoint returns a safe fallback (#13)."""
    import httpx

    mock_instance = MagicMock()
    mock_instance.get = AsyncMock(side_effect=httpx.HTTPError("connection refused"))
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=None)
    mock_client_cls.return_value = mock_instance

    resp = client.get("/ai/usage")

    assert resp.status_code == 200
    data = resp.json()
    assert data["ai_enabled"] is False
    assert data["estimated_cost_usd"] == 0
    assert "error" in data
    assert data["ai_status"] == "unavailable"
    assert data["ai_status_detail"]


@patch("routers.ai.http_client")
def test_ai_usage_ai_status_degraded_with_fallback_detail(mock_client_cls, client: TestClient):
    """#1460: primary down + fallback serving → 'degraded' with detail."""
    mock_cls, _ = _mock_httpx_get_map(
        {
            "usage": {"ai_enabled": True},
            "health": {
                "ai_enabled": True,
                "status": "degraded",
                "reachability": {
                    "llm": {"configured": True, "available": True, "primary_ok": False, "active": "gemini"},
                    "embedding": {"configured": True, "available": True, "primary_ok": True, "active": "ollama"},
                },
            },
        }
    )
    mock_client_cls.side_effect = mock_cls

    resp = client.get("/ai/usage")
    data = resp.json()
    assert data["ai_status"] == "degraded"
    assert "fallback" in data["ai_status_detail"]


@patch("routers.ai.http_client")
def test_ai_usage_ai_status_unavailable_when_no_llm_reachable(mock_client_cls, client: TestClient):
    mock_cls, _ = _mock_httpx_get_map(
        {
            "usage": {"ai_enabled": True},
            "health": {"ai_enabled": True, "status": "unavailable"},
        }
    )
    mock_client_cls.side_effect = mock_cls

    resp = client.get("/ai/usage")
    data = resp.json()
    assert data["ai_status"] == "unavailable"
    assert data["ai_status_detail"]


@patch("routers.ai.http_client")
def test_ai_usage_ai_status_disabled_when_not_configured(mock_client_cls, client: TestClient):
    mock_cls, _ = _mock_httpx_get_map(
        {
            "usage": {"ai_enabled": False},
            "health": {"ai_enabled": False, "status": "degraded"},
        }
    )
    mock_client_cls.side_effect = mock_cls

    resp = client.get("/ai/usage")
    data = resp.json()
    assert data["ai_status"] == "disabled"
    assert data["ai_status_detail"]


@patch("routers.ai.http_client")
def test_ai_usage_ai_status_unavailable_when_health_probe_fails(mock_client_cls, client: TestClient):
    """Usage stats succeed but /health is down → 'unavailable', never 'ok'."""
    import httpx

    def _get(url, **kw):
        if url.endswith("/health"):
            raise httpx.ConnectError("refused")
        r = MagicMock()
        r.json.return_value = {"ai_enabled": True}
        r.raise_for_status = MagicMock()
        return r

    mock_instance = MagicMock()
    mock_instance.get = AsyncMock(side_effect=_get)
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=None)
    mock_client_cls.side_effect = MagicMock(return_value=mock_instance)

    resp = client.get("/ai/usage")
    data = resp.json()
    assert data["ai_status"] == "unavailable"


# --- POST /ai/chat -----------------------------------------------------------


@patch("routers.ai.http_client")
def test_ai_chat_with_valid_message(mock_client_cls, client: TestClient):
    mock_cls, mock_instance = _mock_httpx({"response": "Hello! How can I help?", "suggestions": ["Tell me more"]})
    mock_client_cls.side_effect = mock_cls

    resp = client.post(
        "/ai/chat",
        json={"messages": [{"role": "user", "content": "Hi there"}]},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["response"] == "Hello! How can I help?"
    assert "Tell me more" in data["suggestions"]
    mock_instance.post.assert_awaited_once()


def test_ai_chat_with_empty_messages_validation(client: TestClient):
    """A request missing the required ``messages`` field fails validation."""
    resp = client.post("/ai/chat", json={})
    assert resp.status_code == 422


def test_ai_chat_with_malformed_message_validation(client: TestClient):
    """A message missing the ``content`` field fails validation."""
    resp = client.post("/ai/chat", json={"messages": [{"role": "user"}]})
    assert resp.status_code == 422


@patch("routers.ai.http_client")
def test_ai_chat_service_unavailable(mock_client_cls, client: TestClient):
    """When the AI service is unreachable, chat returns a graceful fallback."""
    import httpx

    mock_instance = MagicMock()
    mock_instance.post = AsyncMock(side_effect=httpx.HTTPError("timeout"))
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=None)
    mock_client_cls.return_value = mock_instance

    resp = client.post(
        "/ai/chat",
        json={"messages": [{"role": "user", "content": "Hi"}]},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "unavailable"
    assert "response" in data


# --- POST /ai/classify -------------------------------------------------------


@patch("routers.ai.http_client")
def test_ai_classify_returns_suggestions(mock_client_cls, client: TestClient):
    mock_cls, mock_instance = _mock_httpx({"note_id": 1, "suggestions": ["work", "urgent"]})
    mock_client_cls.side_effect = mock_cls

    resp = client.post(
        "/ai/classify",
        json={"note_id": 1, "content": "Meeting about project deadline", "existing_tags": []},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["note_id"] == 1
    assert "work" in data["suggestions"]
    mock_instance.post.assert_awaited_once()


@patch("routers.ai.http_client")
def test_ai_classify_service_unavailable(mock_client_cls, client: TestClient):
    """Classify degrades gracefully when the AI service is down."""
    import httpx

    mock_instance = MagicMock()
    mock_instance.post = AsyncMock(side_effect=httpx.HTTPError("refused"))
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=None)
    mock_client_cls.return_value = mock_instance

    resp = client.post(
        "/ai/classify",
        json={"note_id": 2, "content": "Some content"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "unavailable"
    assert data["suggestions"] == []


# --- POST /ai/daily-recap ----------------------------------------------------


@patch("routers.ai.http_client")
def test_ai_daily_recap_returns_summary(mock_client_cls, client: TestClient):
    mock_cls, mock_instance = _mock_httpx({"recap": "You created 3 notes today.", "suggestions": ["Review your goals"]})
    mock_client_cls.side_effect = mock_cls

    resp = client.post("/ai/daily-recap")

    assert resp.status_code == 200
    data = resp.json()
    assert "recap" in data
    mock_instance.post.assert_awaited_once()


@patch("routers.ai.http_client")
def test_ai_daily_recap_with_explicit_date(mock_client_cls, client: TestClient):
    mock_cls, mock_instance = _mock_httpx({"recap": "Summary for the day.", "suggestions": []})
    mock_client_cls.side_effect = mock_cls

    resp = client.post("/ai/daily-recap?target_date=2024-06-15")

    assert resp.status_code == 200
    data = resp.json()
    assert data["recap"] == "Summary for the day."


def test_ai_daily_recap_invalid_date(client: TestClient):
    """An invalid date format returns 400."""
    resp = client.post("/ai/daily-recap?target_date=not-a-date")
    assert resp.status_code == 400
    assert "Invalid date format" in resp.json()["detail"]


@patch("routers.ai.http_client")
def test_ai_daily_recap_service_unavailable(mock_client_cls, client: TestClient):
    """Daily recap degrades gracefully when the AI service is down."""
    import httpx

    mock_instance = MagicMock()
    mock_instance.post = AsyncMock(side_effect=httpx.HTTPError("down"))
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=None)
    mock_client_cls.return_value = mock_instance

    resp = client.post("/ai/daily-recap")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "unavailable"
    assert "recap" in data


# --- POST /ai/plan-suggest ---------------------------------------------------


@patch("routers.ai.http_client")
def test_plan_suggest_forwards_db_built_payload(mock_client_cls, client: TestClient, db_session):
    """The proxy gathers open tasks + cached Google events, then forwards (#1237)."""
    from datetime import UTC, datetime, time

    from models.calendar_task import CalendarTask, CalendarTaskPriority
    from models.google_calendar_event import GoogleCalendarEvent

    db_session.add(CalendarTask(title="Unscheduled task", date=None, priority=CalendarTaskPriority.HIGH))
    db_session.add(CalendarTask(title="Done task", date=None, done=True))
    db_session.add(
        CalendarTask(
            title="Timed task",
            date=datetime(2026, 3, 10).date(),
            start_time=time(9, 0),
            end_time=time(10, 30),
            priority=CalendarTaskPriority.URGENT,
        )
    )
    db_session.add(
        GoogleCalendarEvent(
            user_id=1,
            calendar_id="primary",
            google_id="ev-busy",
            summary="Meeting",
            status="confirmed",
            all_day=False,
            start_at=datetime(2026, 3, 10, 14, 0, tzinfo=UTC),
            end_at=datetime(2026, 3, 10, 15, 0, tzinfo=UTC),
        )
    )
    db_session.commit()

    mock_cls, mock_instance = _mock_httpx(
        {"suggestions": [{"task_id": 1, "date": "2026-03-10", "start_time": "16:00"}], "available": True}
    )
    mock_client_cls.side_effect = mock_cls

    resp = client.post(
        "/ai/plan-suggest",
        json={"week_start": "2026-03-09", "week_end": "2026-03-15", "timezone": "UTC"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert len(data["suggestions"]) == 1

    mock_instance.post.assert_awaited_once()
    payload = mock_instance.post.await_args.kwargs["json"]
    assert payload["week_start"] == "2026-03-09"
    assert payload["week_end"] == "2026-03-15"
    # Done task excluded; unscheduled task included; URGENT timed task first.
    titles = [t["title"] for t in payload["tasks"]]
    assert titles == ["Timed task", "Unscheduled task"]
    timed = payload["tasks"][0]
    assert timed["duration_minutes"] == 90
    # Busy block from the cached Google event.
    assert payload["busy_blocks"] == [{"start": "2026-03-10T14:00:00+00:00", "end": "2026-03-10T15:00:00+00:00"}]


@patch("routers.ai.http_client")
def test_plan_suggest_all_day_event_blocks_local_day(mock_client_cls, client: TestClient, db_session):
    """All-day cache rows are sent as local-day busy blocks (#1237)."""
    from datetime import UTC, datetime

    from models.google_calendar_event import GoogleCalendarEvent

    db_session.add(
        GoogleCalendarEvent(
            user_id=1,
            calendar_id="primary",
            google_id="ev-allday",
            summary="Conference",
            status="confirmed",
            all_day=True,
            start_at=datetime(2026, 3, 11, 0, 0, tzinfo=UTC),
            end_at=datetime(2026, 3, 12, 0, 0, tzinfo=UTC),
        )
    )
    db_session.commit()

    mock_cls, mock_instance = _mock_httpx({"suggestions": [], "available": True})
    mock_client_cls.side_effect = mock_cls

    resp = client.post(
        "/ai/plan-suggest",
        json={"week_start": "2026-03-09", "week_end": "2026-03-15", "timezone": "UTC"},
    )

    assert resp.status_code == 200
    payload = mock_instance.post.await_args.kwargs["json"]
    assert {"start": "2026-03-11T00:00:00", "end": "2026-03-12T00:00:00"} in payload["busy_blocks"]


@patch("routers.ai.http_client")
def test_plan_suggest_unreachable_returns_graceful_fallback(mock_client_cls, client: TestClient):
    """When the AI service is down the endpoint degrades, never 5xx (#1237)."""
    import httpx

    mock_instance = MagicMock()
    mock_instance.post = AsyncMock(side_effect=httpx.HTTPError("down"))
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=None)
    mock_client_cls.return_value = mock_instance

    resp = client.post(
        "/ai/plan-suggest",
        json={"week_start": "2026-03-09", "week_end": "2026-03-15", "timezone": "UTC"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
    assert data["reason"] == "unavailable"
    assert data["suggestions"] == []


def test_plan_suggest_invalid_dates(client: TestClient):
    resp = client.post("/ai/plan-suggest", json={"week_start": "bad", "week_end": "2026-03-15"})
    assert resp.status_code == 400
    resp = client.post("/ai/plan-suggest", json={"week_start": "2026-03-15", "week_end": "2026-03-09"})
    assert resp.status_code == 400


def test_plan_suggest_range_too_large(client: TestClient):
    resp = client.post(
        "/ai/plan-suggest",
        json={"week_start": "2026-01-01", "week_end": "2026-12-31"},
    )
    assert resp.status_code == 400


# --- Chat persistence, history & streaming (#1131) ---------------------------


@pytest.fixture
def clean_chat(db_session):
    """Purge chat_sessions rows that leaked between tests.

    The chat router commits through its own request-scoped session; on the
    SQLite test engine that commit escapes the savepoint fixture, so rows can
    survive into later tests. Deleting + committing here keeps the chat tests
    order-independent. On PostgreSQL the outer test transaction still rolls
    back normally.
    """
    from models.chat_session import ChatSession

    db_session.query(ChatSession).delete()
    db_session.commit()
    yield


@patch("routers.ai.http_client")
def test_ai_chat_persists_session_and_usage_event(mock_client_cls, client: TestClient, db_session, clean_chat):
    """A successful exchange is stored in chat_sessions and tracked in
    usage_events (#1131 AC1+AC4)."""
    from models.chat_session import ChatSession
    from models.usage_event import UsageEvent

    mock_cls, mock_instance = _mock_httpx({"status": "success", "response": "Hi!", "suggestions": ["s"]})
    mock_client_cls.side_effect = mock_cls

    resp = client.post("/ai/chat", json={"messages": [{"role": "user", "content": "hola"}]})

    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"]

    session = db_session.get(ChatSession, data["session_id"])
    assert session is not None
    assert session.user_id == 1
    assert [m["role"] for m in session.messages] == ["user", "assistant"]
    assert session.messages[0]["content"] == "hola"
    assert session.messages[1]["content"] == "Hi!"
    assert session.title == "hola"

    events = db_session.query(UsageEvent).filter(UsageEvent.event_type == "feature_use").all()
    assert any(e.event_data and e.event_data.get("feature") == "ai_chat" for e in events)


@patch("routers.ai.http_client")
def test_ai_chat_retry_does_not_duplicate_user_message(mock_client_cls, client: TestClient, db_session, clean_chat):
    """A frontend retry after an upstream failure must not write the user
    turn twice: the first attempt already committed it (#1131)."""
    import httpx
    from models.chat_session import ChatSession

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "success", "response": "ok", "suggestions": []}
    mock_resp.raise_for_status = MagicMock()

    mock_instance = MagicMock()
    mock_instance.post = AsyncMock(side_effect=[httpx.ConnectError("down"), mock_resp])
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=None)
    mock_client_cls.side_effect = MagicMock(return_value=mock_instance)

    r1 = client.post("/ai/chat", json={"messages": [{"role": "user", "content": "same q"}]})
    assert r1.json()["status"] == "unavailable"
    sid = r1.json()["session_id"]

    # Retry: the persisted tail equals the incoming tail — dedup must kick in.
    r2 = client.post(
        "/ai/chat",
        json={"session_id": sid, "messages": [{"role": "user", "content": "same q"}]},
    )
    assert r2.json()["status"] == "success"

    session = db_session.get(ChatSession, sid)
    # #1460: the failed attempt left an error-marked assistant turn behind,
    # so the retry's user turn is NOT a duplicate of the last stored turn.
    assert [m["role"] for m in session.messages] == ["user", "assistant", "user", "assistant"]
    assert session.messages[1].get("error") is True


@patch("routers.ai.http_client")
def test_ai_chat_failure_persists_error_marked_reply(mock_client_cls, client: TestClient, db_session, clean_chat):
    """#1460: an unreachable ai-service must not leave a dangling user message —
    the session gets an error-marked assistant turn instead."""
    import httpx
    from models.chat_session import ChatSession

    mock_instance = MagicMock()
    mock_instance.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=None)
    mock_client_cls.return_value = mock_instance

    resp = client.post("/ai/chat", json={"messages": [{"role": "user", "content": "hola"}]})
    assert resp.json()["status"] == "unavailable"
    sid = resp.json()["session_id"]

    session = db_session.get(ChatSession, sid)
    assert [m["role"] for m in session.messages] == ["user", "assistant"]
    failed = session.messages[1]
    assert failed.get("error") is True
    assert failed.get("status") == "unavailable"


@patch("routers.ai.http_client")
def test_ai_chat_non_success_status_persists_error_marked_reply(
    mock_client_cls, client: TestClient, db_session, clean_chat
):
    """#1460: a 200-with-degraded-status upstream reply (circuit_open etc.) is
    persisted with the error marker so history shows the exchange failed."""
    from models.chat_session import ChatSession

    mock_cls, mock_instance = _mock_httpx(
        {"status": "circuit_open", "response": "El proveedor de IA se encuentra temporalmente no disponible."}
    )
    mock_client_cls.side_effect = mock_cls

    resp = client.post("/ai/chat", json={"messages": [{"role": "user", "content": "hola"}]})
    sid = resp.json()["session_id"]

    session = db_session.get(ChatSession, sid)
    assert [m["role"] for m in session.messages] == ["user", "assistant"]
    assert session.messages[1].get("error") is True
    assert session.messages[1].get("status") == "circuit_open"


@patch("routers.ai.http_client")
def test_ai_chat_history_roundtrip(mock_client_cls, client: TestClient, db_session, clean_chat):
    """GET /ai/chat/history restores the conversation; DELETE clears it (#1131 AC2)."""
    mock_cls, mock_instance = _mock_httpx({"status": "success", "response": "answer", "suggestions": []})
    mock_client_cls.side_effect = mock_cls

    r = client.post("/ai/chat", json={"messages": [{"role": "user", "content": "pregunta"}]})
    sid = r.json()["session_id"]

    hist = client.get("/ai/chat/history")
    assert hist.status_code == 200
    assert hist.json()["session_id"] == sid
    assert [m["role"] for m in hist.json()["messages"]] == ["user", "assistant"]

    d = client.delete("/ai/chat/history")
    assert d.status_code == 200
    assert d.json()["status"] == "cleared"

    empty = client.get("/ai/chat/history")
    assert empty.json() == {"session_id": None, "messages": []}


def test_ai_chat_history_empty_by_default(client: TestClient, clean_chat):
    resp = client.get("/ai/chat/history")
    assert resp.status_code == 200
    assert resp.json() == {"session_id": None, "messages": []}


def test_ai_chat_rejects_non_user_tail(client: TestClient):
    """A conversation whose last turn is from the assistant is rejected."""
    resp = client.post(
        "/ai/chat",
        json={"messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}]},
    )
    assert resp.status_code == 422


# --- POST /ai/chat/stream (SSE proxy) ----------------------------------------


def _sse_lines(*blocks: tuple) -> list:
    lines = []
    for event, data in blocks:
        lines.append(f"event: {event}")
        lines.append(f"data: {json.dumps(data)}")
        lines.append("")
    return lines


class _FakeStreamResponse:
    def __init__(self, lines: list, status_code: int = 200):
        self.status_code = status_code
        self._lines = lines

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeStreamCM:
    """Async context manager mimicking ``httpx.AsyncClient.stream()``."""

    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self._resp

    async def __aexit__(self, *exc):
        return None


def _mock_streaming_httpx(lines: list, status_code: int = 200) -> MagicMock:
    mock_instance = MagicMock()
    mock_instance.stream = MagicMock(return_value=_FakeStreamCM(_FakeStreamResponse(lines, status_code)))
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=None)
    return MagicMock(return_value=mock_instance)


@patch("routers.ai.http_client")
def test_ai_chat_stream_proxies_sse_and_persists(mock_client_cls, client: TestClient, db_session, clean_chat):
    """The stream endpoint forwards upstream SSE, announces the session id,
    and persists the accumulated assistant reply on the request-scoped
    session (#1131)."""
    from models.chat_session import ChatSession
    from models.usage_event import UsageEvent

    lines = _sse_lines(
        ("meta", {"status": "success", "provider": "fake", "sources": ["Nota A"]}),
        ("token", {"text": "Hola"}),
        ("token", {"text": " mundo"}),
        ("done", {"suggestions": ["otra pregunta"]}),
    )
    mock_client_cls.side_effect = _mock_streaming_httpx(lines)

    resp = client.post("/ai/chat/stream", json={"messages": [{"role": "user", "content": "pregunta"}]})

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    body = resp.text
    assert "event: session" in body
    assert "event: token" in body
    assert '"Hola"' in body
    assert "event: done" in body

    db_session.expire_all()
    session = db_session.query(ChatSession).first()
    assert session is not None
    assert [m["role"] for m in session.messages] == ["user", "assistant"]
    assert session.messages[-1]["content"] == "Hola mundo"

    db_session.expire_all()
    events = db_session.query(UsageEvent).filter(UsageEvent.event_type == "feature_use").all()
    assert any(e.event_data and e.event_data.get("feature") == "ai_chat" for e in events)


@patch("routers.ai.http_client")
def test_ai_chat_stream_upstream_error_frame(mock_client_cls, client: TestClient):
    """A non-200 upstream response surfaces as an SSE error frame, not a 5xx."""
    mock_client_cls.side_effect = _mock_streaming_httpx([], status_code=503)

    resp = client.post("/ai/chat/stream", json={"messages": [{"role": "user", "content": "q"}]})

    assert resp.status_code == 200
    assert "event: session" in resp.text
    assert "event: error" in resp.text
    # #1460: the error frame is structured — error_class lets the UI/logs
    # distinguish a dead provider from a malformed request.
    assert "error_class" in resp.text


@patch("routers.ai.http_client")
def test_ai_chat_stream_failure_persists_error_marked_reply(
    mock_client_cls, client: TestClient, db_session, clean_chat
):
    """#1460: a failed stream still leaves a visible exchange in history —
    error-marked assistant turn, no dangling user message."""
    from models.chat_session import ChatSession

    mock_client_cls.side_effect = _mock_streaming_httpx([], status_code=503)

    resp = client.post("/ai/chat/stream", json={"messages": [{"role": "user", "content": "hola"}]})
    assert resp.status_code == 200

    db_session.expire_all()
    session = db_session.query(ChatSession).first()
    assert session is not None
    assert [m["role"] for m in session.messages] == ["user", "assistant"]
    assert session.messages[1].get("error") is True


@patch("routers.ai.http_client")
def test_ai_chat_stream_upstream_error_event_marks_session(mock_client_cls, client: TestClient, db_session, clean_chat):
    """#1460: an upstream ``event: error`` frame (provider failure mid-stream)
    is forwarded verbatim AND persisted as an error-marked assistant turn."""
    from models.chat_session import ChatSession

    lines = _sse_lines(
        ("meta", {"status": "success", "provider": "fake", "sources": []}),
        ("error", {"status": "error", "message": "Chat failed", "provider": "fake", "error_class": "RuntimeError"}),
    )
    mock_client_cls.side_effect = _mock_streaming_httpx(lines)

    resp = client.post("/ai/chat/stream", json={"messages": [{"role": "user", "content": "hola"}]})
    assert resp.status_code == 200
    assert '"error_class": "RuntimeError"' in resp.text

    db_session.expire_all()
    session = db_session.query(ChatSession).first()
    assert session is not None
    assert [m["role"] for m in session.messages] == ["user", "assistant"]
    assert session.messages[1].get("error") is True
