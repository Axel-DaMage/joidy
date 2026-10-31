"""TestClient-level tests for ai-service FastAPI endpoints.

All provider clients, the rate limiter, the cost tracker and the database
layer are mocked — no real API keys, network or PostgreSQL are needed.
Covers success, provider-failure (500) and circuit-open degradation paths
for /embed, /classify and /rag.
"""

import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import database
import main
import pytest
from circuit_breaker import CircuitState
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
def ai_disabled(monkeypatch):
    """Force `settings.is_ai_enabled` to False deterministically."""
    for key in PROVIDER_KEYS:
        monkeypatch.setattr(settings, key, "")
    monkeypatch.setattr(settings, "ollama_base_url", "")
    monkeypatch.setattr(settings, "internal_secret", "")
    monkeypatch.setattr(settings, "llm_model", "gemini:gemini-2.0-flash")
    monkeypatch.setattr(settings, "embedding_model", "gemini:models/text-embedding-004")
    return settings


@pytest.fixture
def ai_enabled(monkeypatch):
    """Enable AI with fully mocked provider clients and limiter.

    Pins the configured models to the gemini defaults too: a developer .env
    with LLM_MODEL/EMBEDDING_MODEL pointing at another provider (#1159) must
    not change which keys make `is_ai_enabled` True inside these tests.
    """
    for key in PROVIDER_KEYS:
        monkeypatch.setattr(settings, key, "")
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "internal_secret", "")
    monkeypatch.setattr(settings, "llm_model", "gemini:gemini-2.0-flash")
    monkeypatch.setattr(settings, "embedding_model", "gemini:models/text-embedding-004")

    limiter = SimpleNamespace(acquire=AsyncMock())
    monkeypatch.setattr(main, "get_limiter", lambda *a, **k: limiter)
    monkeypatch.setattr(main, "record_usage", MagicMock())

    llm = SimpleNamespace(
        provider_name="fake-llm",
        generate=AsyncMock(return_value="llm answer"),
        classify=AsyncMock(return_value=[{"tag": "testing", "confidence": 0.9, "is_new": True}]),
        health_check=AsyncMock(return_value=True),
    )
    emb = SimpleNamespace(
        provider_name="fake-emb",
        embed=AsyncMock(return_value=[0.1, 0.2, 0.3]),
        health_check=AsyncMock(return_value=True),
    )
    monkeypatch.setattr(main, "get_llm_client", lambda: llm)
    monkeypatch.setattr(main, "get_embedding_client", lambda: emb)

    store_embedding = MagicMock()
    monkeypatch.setattr(database, "store_embedding", store_embedding)
    return SimpleNamespace(llm=llm, emb=emb, limiter=limiter, store_embedding=store_embedding)


def _client() -> TestClient:
    return TestClient(main.app)


# ── health / metadata endpoints ────────────────────────────────────────


class TestHealthAndMetadata:
    def test_health_degraded_when_no_providers(self, ai_disabled):
        resp = _client().get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["ai_enabled"] is False

    def test_health_ok_when_providers_configured(self, ai_enabled):
        resp = _client().get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert resp.json()["ai_enabled"] is True

    def test_metrics_endpoint(self, ai_disabled):
        resp = _client().get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]

    def test_providers_endpoint(self, ai_enabled):
        resp = _client().get("/providers")
        assert resp.status_code == 200
        assert "gemini" in resp.json()["available"]


# ── /embed ─────────────────────────────────────────────────────────────


class TestEmbedEndpoint:
    def test_disabled_when_ai_not_configured(self, ai_disabled):
        resp = _client().post("/embed", json={"note_id": 1, "content": "hello"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"

    def test_success_returns_embedding_and_stores_it(self, ai_enabled):
        resp = _client().post("/embed", json={"note_id": 7, "content": "hello"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["note_id"] == 7
        assert body["embedding"] == [0.1, 0.2, 0.3]
        assert body["provider"] == "fake-emb"
        ai_enabled.store_embedding.assert_called_once_with(7, [0.1, 0.2, 0.3])
        ai_enabled.emb.embed.assert_awaited_once_with("hello")

    def test_provider_failure_returns_500(self, ai_enabled):
        ai_enabled.emb.embed = AsyncMock(side_effect=RuntimeError("provider down"))
        resp = _client().post("/embed", json={"note_id": 1, "content": "x"})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Embedding failed"

    def test_circuit_open_returns_degraded_not_500(self, ai_enabled):
        main.emb_circuit_breaker.state = CircuitState.OPEN
        main.emb_circuit_breaker.last_failure_time = time.time()
        resp = _client().post("/embed", json={"note_id": 1, "content": "x"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "circuit_open"
        ai_enabled.emb.embed.assert_not_awaited()

    def test_cache_hit_skips_provider_call(self, ai_enabled):
        client = _client()
        payload = {"note_id": 3, "content": "cache me"}
        assert client.post("/embed", json=payload).json()["status"] == "success"
        resp = client.post("/embed", json=payload)
        assert resp.json()["status"] == "success"
        assert resp.json()["provider"] == "gemini"  # model prefix on cache hit
        ai_enabled.emb.embed.assert_awaited_once()

    def test_invalid_payload_returns_422(self, ai_disabled):
        resp = _client().post("/embed", json={"note_id": "not-an-int"})
        assert resp.status_code == 422


# ── /classify ──────────────────────────────────────────────────────────


class TestClassifyEndpoint:
    def test_disabled_when_ai_not_configured(self, ai_disabled):
        resp = _client().post("/classify", json={"note_id": 1, "content": "c", "existing_tags": []})
        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"
        assert resp.json()["suggestions"] == []

    def test_success_returns_suggestions(self, ai_enabled):
        resp = _client().post(
            "/classify",
            json={"note_id": 2, "content": "some note", "existing_tags": ["old"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["suggestions"] == [{"tag": "testing", "confidence": 0.9, "is_new": True}]
        assert body["provider"] == "fake-llm"

    def test_provider_failure_returns_500(self, ai_enabled):
        ai_enabled.llm.classify = AsyncMock(side_effect=RuntimeError("down"))
        resp = _client().post("/classify", json={"note_id": 1, "content": "c"})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Classification failed"

    def test_circuit_open_returns_degraded(self, ai_enabled):
        main.llm_circuit_breaker.state = CircuitState.OPEN
        main.llm_circuit_breaker.last_failure_time = time.time()
        resp = _client().post("/classify", json={"note_id": 1, "content": "c"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "circuit_open"
        assert resp.json()["suggestions"] == []


# ── /rag ───────────────────────────────────────────────────────────────


class TestRagEndpoint:
    def test_disabled_when_ai_not_configured(self, ai_disabled):
        resp = _client().post("/rag", json={"question": "q?"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"

    def test_success_returns_answer(self, ai_enabled, monkeypatch):
        monkeypatch.setattr(database, "find_similar_notes", lambda vec, limit=5: [{"note_id": 7, "distance": 0.2}])
        engine = MagicMock()
        conn = engine.connect.return_value.__enter__.return_value
        conn.execute.return_value.fetchone.return_value = ("Note title", "note body")
        monkeypatch.setattr(database, "engine", engine)

        resp = _client().post("/rag", json={"question": "what did I learn?", "top_k": 3})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["answer"] == "llm answer"
        assert body["provider"] == "fake-llm"
        ai_enabled.emb.embed.assert_awaited_once_with("what did I learn?")
        ai_enabled.llm.generate.assert_awaited_once()

    def test_provider_failure_returns_500(self, ai_enabled):
        ai_enabled.emb.embed = AsyncMock(side_effect=RuntimeError("embed down"))
        resp = _client().post("/rag", json={"question": "q?"})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "RAG failed"

    def test_circuit_open_returns_degraded(self, ai_enabled):
        main.emb_circuit_breaker.state = CircuitState.OPEN
        main.emb_circuit_breaker.last_failure_time = time.time()
        resp = _client().post("/rag", json={"question": "q?"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "circuit_open"
        assert "error" in body


# ── /chat (sanity) ─────────────────────────────────────────────────────


class TestChatEndpoint:
    def test_disabled_when_ai_not_configured(self, ai_disabled):
        resp = _client().post("/chat", json={"messages": [{"role": "user", "content": "hi"}]})
        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"

    def test_success_returns_response(self, ai_enabled):
        resp = _client().post("/chat", json={"messages": [{"role": "user", "content": "hi"}]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["response"] == "llm answer"

    def test_empty_messages_returns_422(self, ai_enabled):
        resp = _client().post("/chat", json={"messages": []})
        assert resp.status_code == 422


# ── internal auth middleware ───────────────────────────────────────────


class TestInternalAuth:
    def test_secret_enforced_on_data_endpoints(self, ai_enabled, monkeypatch):
        monkeypatch.setattr(settings, "internal_secret", "s3cr3t")
        client = _client()

        resp = client.post("/embed", json={"note_id": 1, "content": "x"})
        assert resp.status_code == 403

        resp = client.post(
            "/embed",
            json={"note_id": 1, "content": "x"},
            headers={"X-Internal-Secret": "s3cr3t"},
        )
        assert resp.status_code == 200

    def test_health_public_even_with_secret(self, ai_enabled, monkeypatch):
        monkeypatch.setattr(settings, "internal_secret", "s3cr3t")
        assert _client().get("/health").status_code == 200


if __name__ == "__main__":
    unittest.main()
