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
    # Pin to non-production: with no internal_secret a developer .env set to
    # APP_ENV=production would make the fail-closed middleware (#1277) return
    # 503 for every endpoint test below.
    monkeypatch.setattr(settings, "app_env", "development")
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
    # Pin to non-production so the fail-closed middleware (#1277) does not
    # reject requests when INTERNAL_SECRET is empty.
    monkeypatch.setattr(settings, "app_env", "development")
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


# ── /classify cache-key ambiguity (#1330) ──────────────────────────────


class TestClassifyCacheKeys:
    def test_comma_containing_tags_produce_distinct_keys(self, ai_enabled):
        """["a,b","c"] and ["a","b,c"] must not share a cache entry."""
        client = _client()
        base = {"note_id": 1, "content": "same content"}

        r1 = client.post("/classify", json={**base, "existing_tags": ["a,b", "c"]})
        r2 = client.post("/classify", json={**base, "existing_tags": ["a", "b,c"]})
        assert r1.json()["status"] == "success"
        assert r2.json()["status"] == "success"
        # If the two tag lists collapsed into one key, the second request
        # would be a cache hit and classify would only be awaited once.
        assert ai_enabled.llm.classify.await_count == 2

        # An identical repeat request IS a cache hit — still only 2 calls.
        r3 = client.post("/classify", json={**base, "existing_tags": ["a,b", "c"]})
        assert r3.json()["status"] == "success"
        assert ai_enabled.llm.classify.await_count == 2


# ── /cluster ───────────────────────────────────────────────────────────


def _mock_cluster_db(monkeypatch, rows):
    """Point /cluster's engine at a fake connection returning `rows`."""
    engine = MagicMock()
    conn = engine.connect.return_value.__enter__.return_value
    conn.execute.return_value.fetchall.return_value = rows
    monkeypatch.setattr(database, "engine", engine)


class TestClusterEndpoint:
    def test_malformed_embedding_row_returns_422(self, ai_disabled, monkeypatch):
        _mock_cluster_db(
            monkeypatch,
            [(1, "[0.1,0.2,0.3]"), (2, "not-a-vector"), (3, "[0.4,0.5,0.6]")],
        )
        resp = _client().post("/cluster?min_samples=1")
        assert resp.status_code == 422
        assert "Malformed embedding" in resp.json()["detail"]

    def test_ragged_embedding_dimensions_returns_422(self, ai_disabled, monkeypatch):
        _mock_cluster_db(
            monkeypatch,
            [(1, "[0.1,0.2,0.3]"), (2, "[0.4,0.5]"), (3, "[0.6,0.7,0.8]")],
        )
        resp = _client().post("/cluster?min_samples=1")
        assert resp.status_code == 422

    def test_valid_embeddings_do_not_422(self, ai_disabled, monkeypatch):
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
        assert "clusters" in resp.json()

    def test_too_few_notes_short_circuits(self, ai_disabled, monkeypatch):
        _mock_cluster_db(monkeypatch, [(1, "[0.1,0.2]")])
        resp = _client().post("/cluster?min_samples=5")
        assert resp.status_code == 200
        assert resp.json()["clusters"] == []


# ── /chat prompt delimiters (#1330) ────────────────────────────────────


class TestChatPromptDelimiters:
    def test_messages_wrapped_in_delimiters(self, ai_enabled):
        resp = _client().post(
            "/chat",
            json={
                "messages": [
                    {"role": "user", "content": "hola"},
                    {"role": "assistant", "content": "¡buenas!"},
                    {"role": "user", "content": "resume mis notas"},
                ]
            },
        )
        assert resp.json()["status"] == "success"
        kwargs = ai_enabled.llm.generate.call_args.kwargs
        assert '<chat_message role="user">' in kwargs["prompt"]
        assert "resume mis notas" in kwargs["prompt"]
        assert "</chat_message>" in kwargs["prompt"]
        assert "<personal_context>" in kwargs["system_prompt"]


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

    def test_fail_closed_in_production_without_secret(self, ai_enabled, monkeypatch):
        # #1277: a production deployment missing INTERNAL_SECRET must refuse
        # data endpoints instead of serving them unauthenticated.
        monkeypatch.setattr(settings, "app_env", "production")
        monkeypatch.setattr(settings, "internal_secret", "")
        resp = _client().post("/embed", json={"note_id": 1, "content": "x"})
        assert resp.status_code == 503

    def test_health_and_metrics_public_in_production_without_secret(self, ai_enabled, monkeypatch):
        monkeypatch.setattr(settings, "app_env", "production")
        monkeypatch.setattr(settings, "internal_secret", "")
        client = _client()
        assert client.get("/health").status_code == 200
        assert client.get("/metrics").status_code == 200

    def test_permissive_in_dev_without_secret(self, ai_enabled):
        # Non-production stays permissive when INTERNAL_SECRET is unset.
        resp = _client().post("/embed", json={"note_id": 1, "content": "x"})
        assert resp.status_code == 200


if __name__ == "__main__":
    unittest.main()
