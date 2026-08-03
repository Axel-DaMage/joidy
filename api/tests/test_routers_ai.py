"""Tests for /ai router endpoints (#13).

The AI service runs in a separate container, so all outbound ``httpx`` calls
are mocked. These tests cover the chat, classify, usage, and daily-recap
endpoints, including graceful degradation when the AI service is unreachable.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


def _mock_httpx(response_json: dict) -> tuple[MagicMock, MagicMock]:
    """Build a mocked ``httpx.AsyncClient`` async-context-manager.

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


@patch("routers.ai.httpx.AsyncClient")
def test_ai_usage_returns_data(mock_client_cls, client: TestClient):
    mock_cls, mock_instance = _mock_httpx({"ai_enabled": True, "estimated_cost_usd": 1.23, "tokens": 5000})
    mock_client_cls.side_effect = mock_cls

    resp = client.get("/ai/usage")

    assert resp.status_code == 200
    data = resp.json()
    assert data["ai_enabled"] is True
    assert data["estimated_cost_usd"] == 1.23
    mock_instance.get.assert_awaited_once()


@patch("routers.ai.httpx.AsyncClient")
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


@patch("routers.ai.httpx.AsyncClient")
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


@patch("routers.ai.httpx.AsyncClient")
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


@patch("routers.ai.httpx.AsyncClient")
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


@patch("routers.ai.httpx.AsyncClient")
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


@patch("routers.ai.httpx.AsyncClient")
def test_ai_daily_recap_returns_summary(mock_client_cls, client: TestClient):
    mock_cls, mock_instance = _mock_httpx({"recap": "You created 3 notes today.", "suggestions": ["Review your goals"]})
    mock_client_cls.side_effect = mock_cls

    resp = client.post("/ai/daily-recap")

    assert resp.status_code == 200
    data = resp.json()
    assert "recap" in data
    mock_instance.post.assert_awaited_once()


@patch("routers.ai.httpx.AsyncClient")
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


@patch("routers.ai.httpx.AsyncClient")
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
