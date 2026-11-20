"""Tests for /ai router endpoints (#13).

The AI service runs in a separate container, so all outbound ``httpx`` calls
are mocked. These tests cover the chat, classify, usage, and daily-recap
endpoints, including graceful degradation when the AI service is unreachable.
"""

from unittest.mock import AsyncMock, MagicMock, patch

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


@patch("routers.ai.http_client")
def test_ai_usage_returns_data(mock_client_cls, client: TestClient):
    mock_cls, mock_instance = _mock_httpx({"ai_enabled": True, "estimated_cost_usd": 1.23, "tokens": 5000})
    mock_client_cls.side_effect = mock_cls

    resp = client.get("/ai/usage")

    assert resp.status_code == 200
    data = resp.json()
    assert data["ai_enabled"] is True
    assert data["estimated_cost_usd"] == 1.23
    mock_instance.get.assert_awaited_once()


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
