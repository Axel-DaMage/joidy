"""Input-bound tests for ai-service endpoints (#1324).

Oversized text, oversized batches and out-of-range numeric parameters must be
rejected with 422 by request validation — before any provider call, database
query or CPU-bound work runs. All provider clients, the rate limiter and the
database layer are mocked; no API keys, network or PostgreSQL are needed.
"""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import database
import main
import pytest
from config import settings
from fastapi.testclient import TestClient

PROVIDER_KEYS = (
    "gemini_api_key",
    "openai_api_key",
    "anthropic_api_key",
    "openrouter_api_key",
    "cohere_api_key",
)


@pytest.fixture
def safe_settings(monkeypatch):
    """No providers, no internal secret, non-production env.

    Validation runs before the endpoint body, so 422 assertions hold
    regardless of `is_ai_enabled`; a well-formed request falls through to the
    standard ``status: disabled`` response.
    """
    for key in PROVIDER_KEYS:
        monkeypatch.setattr(settings, key, "")
    monkeypatch.setattr(settings, "ollama_base_url", "")
    monkeypatch.setattr(settings, "internal_secret", "")
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "llm_model", "gemini:gemini-2.0-flash")
    monkeypatch.setattr(settings, "embedding_model", "gemini:models/text-embedding-004")
    return settings


@pytest.fixture
def ai_enabled(safe_settings, monkeypatch):
    """Enable AI (gemini key) with the rate limiter mocked out."""
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    limiter = SimpleNamespace(acquire=AsyncMock())
    monkeypatch.setattr(main, "get_limiter", lambda *a, **k: limiter)
    local_limiter = SimpleNamespace(acquire=AsyncMock())
    monkeypatch.setattr(main, "get_local_limiter", lambda *a, **k: local_limiter)
    return SimpleNamespace(limiter=limiter, local_limiter=local_limiter)


def _client() -> TestClient:
    return TestClient(main.app)


def _mock_cluster_db(monkeypatch, rows):
    engine = MagicMock()
    conn = engine.connect.return_value.__enter__.return_value
    conn.execute.return_value.fetchall.return_value = rows
    monkeypatch.setattr(database, "engine", engine)


# ── /embed ─────────────────────────────────────────────────────────────


class TestEmbedBounds:
    def test_content_over_limit_returns_422(self, safe_settings):
        resp = _client().post(
            "/embed",
            json={"note_id": 1, "content": "x" * (settings.max_embed_content_chars + 1)},
        )
        assert resp.status_code == 422

    def test_content_at_limit_passes_validation(self, safe_settings):
        resp = _client().post(
            "/embed",
            json={"note_id": 1, "content": "x" * settings.max_embed_content_chars},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"


# ── /classify ──────────────────────────────────────────────────────────


class TestClassifyBounds:
    def test_content_over_limit_returns_422(self, safe_settings):
        resp = _client().post(
            "/classify",
            json={"note_id": 1, "content": "x" * (settings.max_classify_content_chars + 1)},
        )
        assert resp.status_code == 422

    def test_too_many_existing_tags_returns_422(self, safe_settings):
        resp = _client().post(
            "/classify",
            json={
                "note_id": 1,
                "content": "c",
                "existing_tags": ["t"] * (settings.max_classify_tag_items + 1),
            },
        )
        assert resp.status_code == 422

    def test_oversized_tag_returns_422(self, safe_settings):
        resp = _client().post(
            "/classify",
            json={
                "note_id": 1,
                "content": "c",
                "existing_tags": ["t" * (settings.max_tag_chars + 1)],
            },
        )
        assert resp.status_code == 422

    def test_valid_payload_passes_validation(self, safe_settings):
        resp = _client().post(
            "/classify",
            json={"note_id": 1, "content": "c", "existing_tags": ["tag"]},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"


# ── /rag ───────────────────────────────────────────────────────────────


class TestRagBounds:
    def test_question_over_limit_returns_422(self, safe_settings):
        resp = _client().post(
            "/rag",
            json={"question": "q" * (settings.max_rag_question_chars + 1)},
        )
        assert resp.status_code == 422

    def test_top_k_zero_returns_422(self, safe_settings):
        resp = _client().post("/rag", json={"question": "q?", "top_k": 0})
        assert resp.status_code == 422

    def test_top_k_over_limit_returns_422(self, safe_settings):
        resp = _client().post(
            "/rag",
            json={"question": "q?", "top_k": settings.max_rag_top_k + 1},
        )
        assert resp.status_code == 422

    def test_valid_payload_passes_validation(self, safe_settings):
        resp = _client().post("/rag", json={"question": "q?", "top_k": settings.max_rag_top_k})
        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"


# ── /chat ──────────────────────────────────────────────────────────────


class TestChatBounds:
    def test_one_mb_message_returns_422(self, safe_settings):
        """Issue verification: chat with 1MB content must be rejected."""
        resp = _client().post(
            "/chat",
            json={"messages": [{"role": "user", "content": "x" * 1_000_000}]},
        )
        assert resp.status_code == 422

    def test_too_many_messages_returns_422(self, safe_settings):
        resp = _client().post(
            "/chat",
            json={
                "messages": [
                    {"role": "user" if i % 2 == 0 else "assistant", "content": "hi"}
                    for i in range(settings.max_chat_messages)
                ]
                + [{"role": "user", "content": "hi"}]
            },
        )
        assert resp.status_code == 422

    def test_empty_messages_returns_422(self, safe_settings):
        resp = _client().post("/chat", json={"messages": []})
        assert resp.status_code == 422

    def test_oversized_role_returns_422(self, safe_settings):
        resp = _client().post(
            "/chat",
            json={"messages": [{"role": "u" * 21, "content": "hi"}]},
        )
        assert resp.status_code == 422

    def test_too_many_context_items_returns_422(self, safe_settings):
        resp = _client().post(
            "/chat",
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "context": {"top_tags": ["t"] * (settings.max_chat_context_items + 1)},
            },
        )
        assert resp.status_code == 422

    def test_oversized_context_item_returns_422(self, safe_settings):
        resp = _client().post(
            "/chat",
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "context": {"recent_notes": ["n" * (settings.max_chat_context_item_chars + 1)]},
            },
        )
        assert resp.status_code == 422

    def test_negative_xp_returns_422(self, safe_settings):
        resp = _client().post(
            "/chat",
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "context": {"xp": -5},
            },
        )
        assert resp.status_code == 422

    def test_valid_payload_passes_validation(self, safe_settings):
        resp = _client().post(
            "/chat",
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "context": {
                    "goals": [{"title": "g"}],
                    "top_tags": ["a"],
                    "recent_notes": ["note"],
                    "xp": 10,
                },
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"


# ── /cluster ───────────────────────────────────────────────────────────


class TestClusterBounds:
    def test_max_notes_one_million_returns_422(self, safe_settings):
        """Issue verification: POST /cluster?max_notes=1000000 must be 422."""
        resp = _client().post("/cluster?max_notes=1000000")
        assert resp.status_code == 422

    def test_max_notes_zero_returns_422(self, safe_settings):
        resp = _client().post("/cluster?max_notes=0")
        assert resp.status_code == 422

    def test_min_samples_out_of_range_returns_422(self, safe_settings):
        assert _client().post("/cluster?min_samples=0").status_code == 422
        resp = _client().post(f"/cluster?min_samples={settings.max_cluster_min_samples + 1}")
        assert resp.status_code == 422

    def test_eps_out_of_range_returns_422(self, safe_settings):
        assert _client().post("/cluster?eps=0").status_code == 422
        assert _client().post("/cluster?eps=-0.5").status_code == 422
        assert _client().post("/cluster?eps=2.5").status_code == 422

    def test_boundary_values_pass_validation(self, ai_enabled, monkeypatch):
        _mock_cluster_db(monkeypatch, [])
        resp = _client().post(
            f"/cluster?eps=2.0&min_samples={settings.max_cluster_min_samples}&max_notes={settings.max_cluster_notes}"
        )
        assert resp.status_code == 200

    def test_acquires_rate_limit_slot(self, ai_enabled, monkeypatch):
        """The CPU-heavy DBSCAN fit stays rate-limited — on its own local
        bucket, not the shared provider budget it would convoy (#1539)."""
        _mock_cluster_db(monkeypatch, [])
        resp = _client().post("/cluster")
        assert resp.status_code == 200
        ai_enabled.local_limiter.acquire.assert_awaited_once()
        ai_enabled.limiter.acquire.assert_not_awaited()

    def test_dbscan_runs_off_event_loop(self, ai_enabled, monkeypatch):
        """The O(n²) DBSCAN fit must not block the event loop (#1324)."""
        calls: list[str] = []
        real_to_thread = asyncio.to_thread

        async def spy(fn, *args, **kwargs):
            calls.append(fn.__name__)
            return await real_to_thread(fn, *args, **kwargs)

        monkeypatch.setattr(main.asyncio, "to_thread", spy)
        _mock_cluster_db(
            monkeypatch,
            [
                (1, "[1.0,0.0]"),
                (2, "[0.9,0.1]"),
                (3, "[0.0,1.0]"),
                (4, "[0.1,0.9]"),
            ],
        )
        resp = _client().post("/cluster?eps=2.0&min_samples=1")
        assert resp.status_code == 200
        assert "_parse_and_cluster" in calls


# ── /daily-recap ───────────────────────────────────────────────────────


class TestDailyRecapBounds:
    def test_invalid_date_returns_422(self, safe_settings):
        resp = _client().post("/daily-recap", json={"date": "not-a-date"})
        assert resp.status_code == 422

    def test_too_many_note_titles_returns_422(self, safe_settings):
        resp = _client().post(
            "/daily-recap",
            json={
                "date": "2025-01-15",
                "note_titles": ["t"] * (settings.max_recap_note_titles + 1),
            },
        )
        assert resp.status_code == 422

    def test_oversized_note_title_returns_422(self, safe_settings):
        resp = _client().post(
            "/daily-recap",
            json={
                "date": "2025-01-15",
                "note_titles": ["t" * (settings.max_recap_title_chars + 1)],
            },
        )
        assert resp.status_code == 422

    def test_negative_counter_returns_422(self, safe_settings):
        resp = _client().post("/daily-recap", json={"date": "2025-01-15", "xp_gained": -1})
        assert resp.status_code == 422

    def test_valid_payload_passes_validation(self, safe_settings):
        resp = _client().post(
            "/daily-recap",
            json={"date": "2025-01-15", "notes_created": 2, "note_titles": ["a", "b"]},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"


if __name__ == "__main__":
    unittest.main()
