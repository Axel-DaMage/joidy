"""TestClient-level tests for ai-service FastAPI endpoints.

All provider clients, the rate limiter, the cost tracker and the database
layer are mocked — no real API keys, network or PostgreSQL are needed.
Covers success, provider-failure (500) and circuit-open degradation paths
for /embed, /classify and /rag.
"""

import asyncio
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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

    def test_providers_endpoint(self, ai_enabled, monkeypatch):
        monkeypatch.setattr(settings, "internal_secret", "s3cr3t")
        resp = _client().get("/providers", headers={"X-Internal-Secret": "s3cr3t"})
        assert resp.status_code == 200
        assert "gemini" in resp.json()["available"]

    def test_providers_forbidden_without_secret(self, ai_enabled):
        """#1291: /providers fails closed — 403 even when INTERNAL_SECRET is
        not configured, so the config map is never publicly readable."""
        resp = _client().get("/providers")
        assert resp.status_code == 403

    def test_providers_forbidden_with_wrong_secret(self, ai_enabled, monkeypatch):
        """#1288/#1291: wrong secrets of any length are rejected."""
        monkeypatch.setattr(settings, "internal_secret", "s3cr3t")
        for bad in ("x", "s3cr3", "s3cr3t-plus-extra"):
            resp = _client().get("/providers", headers={"X-Internal-Secret": bad})
            assert resp.status_code == 403, bad

    def test_health_hides_provider_inventory_unauthenticated(self, ai_enabled, monkeypatch):
        """#1291: public /health returns no provider/model inventory."""
        monkeypatch.setattr(settings, "internal_secret", "s3cr3t")
        resp = _client().get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["embedding_available"] is True
        assert "provider" not in body
        assert "fallback_enabled" not in body
        assert "gemini" not in str(body)

    def test_health_provider_details_with_internal_secret(self, ai_enabled, monkeypatch):
        """Internal callers with a valid secret still get the inventory."""
        monkeypatch.setattr(settings, "internal_secret", "s3cr3t")
        resp = _client().get("/health", headers={"X-Internal-Secret": "s3cr3t"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["provider"]["llm"]["provider"] == "gemini"
        assert "fallback_enabled" in body

    def test_health_provider_details_hidden_when_secret_unset(self, ai_enabled):
        """With no INTERNAL_SECRET configured, nobody gets the inventory."""
        body = _client().get("/health").json()
        assert "provider" not in body
        assert "fallback_enabled" not in body
        assert body["embedding_available"] is True


class TestHealthReachability:
    """/health reports REAL provider reachability, not just config (#1460)."""

    def test_health_unavailable_when_no_llm_provider_reachable(self, ai_enabled):
        ai_enabled.llm.health_check = AsyncMock(return_value=False)
        body = _client().get("/health").json()
        assert body["status"] == "unavailable"
        assert body["llm_available"] is False
        # Embeddings up but chat can't be served → still unavailable.
        assert body["embedding_available"] is True

    def test_health_degraded_when_llm_primary_down_but_fallback_up(self, ai_enabled, monkeypatch):
        chain_client = SimpleNamespace(
            provider_name="primary",
            chain=[
                SimpleNamespace(provider_name="primary", health_check=AsyncMock(return_value=False)),
                SimpleNamespace(provider_name="fallback", health_check=AsyncMock(return_value=True)),
            ],
        )
        monkeypatch.setattr(main, "get_llm_client", lambda: chain_client)
        body = _client().get("/health").json()
        assert body["status"] == "degraded"
        assert body["llm_available"] is True

    def test_health_degraded_when_embedding_unreachable(self, ai_enabled):
        ai_enabled.emb.health_check = AsyncMock(return_value=False)
        body = _client().get("/health").json()
        assert body["status"] == "degraded"
        assert body["embedding_available"] is False
        assert body["llm_available"] is True

    def test_health_probe_result_cached_within_ttl(self, ai_enabled):
        client = _client()
        assert client.get("/health").status_code == 200
        assert client.get("/health").status_code == 200
        # Second request served from the probe cache — no extra provider pings.
        ai_enabled.llm.health_check.assert_awaited_once()
        ai_enabled.emb.health_check.assert_awaited_once()

    def test_health_reachability_detail_requires_secret(self, ai_enabled, monkeypatch):
        monkeypatch.setattr(settings, "internal_secret", "s3cr3t")

        public_body = _client().get("/health").json()
        assert "reachability" not in public_body

        body = _client().get("/health", headers={"X-Internal-Secret": "s3cr3t"}).json()
        reach = body["reachability"]
        assert reach["llm"]["providers"] == {"fake-llm": True}
        assert reach["llm"]["active"] == "fake-llm"
        assert reach["llm"]["primary_ok"] is True


# ── /embed ─────────────────────────────────────────────────────────────


class TestEmbedEndpoint:
    def test_disabled_when_ai_not_configured(self, ai_disabled):
        resp = _client().post("/embed", json={"note_id": 1, "content": "hello"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"

    def test_success_stores_embedding_without_returning_it(self, ai_enabled):
        """#1541: the vector is persisted but not serialized back unless the
        caller opts in — the only embed-and-store caller never reads it."""
        resp = _client().post("/embed", json={"note_id": 7, "content": "hello"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["note_id"] == 7
        assert "embedding" not in body
        assert body["provider"] == "fake-emb"
        ai_enabled.store_embedding.assert_called_once_with(7, [0.1, 0.2, 0.3])
        ai_enabled.emb.embed.assert_awaited_once_with("hello")

    def test_include_vector_returns_embedding(self, ai_enabled):
        """#1541: include_vector=true keeps the vector available for callers
        that consume it (api semantic search)."""
        resp = _client().post("/embed", json={"note_id": 7, "content": "hello", "include_vector": True})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["embedding"] == [0.1, 0.2, 0.3]
        ai_enabled.store_embedding.assert_called_once_with(7, [0.1, 0.2, 0.3])

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
        monkeypatch.setattr(
            database,
            "find_similar_note_chunks",
            lambda vec, limit, snippet_chars: [{"note_id": 7, "title": "Note title", "snippet": "note body"}],
        )

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

    def test_provider_failure_500_includes_error_class(self, ai_enabled):
        """#1460: a dead provider must not collapse into a bare 'Chat failed'
        — the 500 detail carries provider + exception class for diagnosis."""
        ai_enabled.llm.generate = AsyncMock(side_effect=RuntimeError("quota exceeded"))
        resp = _client().post("/chat", json={"messages": [{"role": "user", "content": "hi"}]})
        assert resp.status_code == 500
        detail = resp.json()["detail"]
        assert "RuntimeError" in detail
        assert "fake-llm" in detail

    def test_stream_provider_failure_emits_structured_error(self, ai_enabled):
        """#1460: stream errors carry provider + error_class in the SSE frame."""
        ai_enabled.llm.generate = AsyncMock(side_effect=RuntimeError("boom"))
        resp = _client().post(
            "/chat",
            json={"messages": [{"role": "user", "content": "hi"}], "stream": True},
        )
        assert resp.status_code == 200
        assert "event: error" in resp.text
        assert '"error_class": "RuntimeError"' in resp.text
        assert '"provider": "fake-llm"' in resp.text


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
    def test_disabled_when_ai_not_configured(self, ai_disabled):
        resp = _client().post("/cluster")
        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"
        assert resp.json()["clusters"] == []

    def test_malformed_embedding_row_returns_422(self, ai_enabled, monkeypatch):
        _mock_cluster_db(
            monkeypatch,
            [(1, "[0.1,0.2,0.3]"), (2, "not-a-vector"), (3, "[0.4,0.5,0.6]")],
        )
        resp = _client().post("/cluster?min_samples=1")
        assert resp.status_code == 422
        assert "Malformed embedding" in resp.json()["detail"]

    def test_ragged_embedding_dimensions_returns_422(self, ai_enabled, monkeypatch):
        _mock_cluster_db(
            monkeypatch,
            [(1, "[0.1,0.2,0.3]"), (2, "[0.4,0.5]"), (3, "[0.6,0.7,0.8]")],
        )
        resp = _client().post("/cluster?min_samples=1")
        assert resp.status_code == 422

    def test_valid_embeddings_do_not_422(self, ai_enabled, monkeypatch):
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

    def test_too_few_notes_short_circuits(self, ai_enabled, monkeypatch):
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

    def test_secret_rejected_regardless_of_length(self, ai_enabled, monkeypatch):
        """#1288: hmac.compare_digest rejects any non-matching secret —
        including prefix matches and length mismatches."""
        monkeypatch.setattr(settings, "internal_secret", "s3cr3t")
        for bad in ("x", "s3cr3", "s3cr3t0", "s3cr3t-s3cr3t"):
            resp = _client().post(
                "/embed",
                json={"note_id": 1, "content": "x"},
                headers={"X-Internal-Secret": bad},
            )
            assert resp.status_code == 403, bad

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


# ── /chat RAG grounding + streaming (#1131) ────────────────────────────────


def _mock_rag_db(monkeypatch, rows: list[tuple[str, str]]):
    """Point the shared retrieval helper at a fake DB returning ``rows`` of
    ``(title, content)`` — one per matched embedding."""
    monkeypatch.setattr(
        database,
        "find_similar_note_chunks",
        lambda vec, limit, snippet_chars: [
            {"note_id": i + 1, "title": t, "snippet": c} for i, (t, c) in enumerate(rows)
        ],
    )


class TestChatRag:
    def test_chat_grounds_answer_in_retrieved_notes(self, ai_enabled, monkeypatch):
        """Retrieved note excerpts land in the system prompt and titles are
        exposed as ``sources`` (#1131 AC1)."""
        _mock_rag_db(monkeypatch, [("My Note", "the thing I learned")])

        resp = _client().post("/chat", json={"messages": [{"role": "user", "content": "qué aprendí?"}]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["sources"] == ["My Note"]
        kwargs = ai_enabled.llm.generate.call_args.kwargs
        assert "<retrieved_notes>" in kwargs["system_prompt"]
        assert "the thing I learned" in kwargs["system_prompt"]

    def test_chat_retrieval_failure_degrades_gracefully(self, ai_enabled):
        """When the embeddings store is unreachable the chat still answers
        with personal-context only — never a 500 (#1131)."""
        # No DB mocks: find_similar_note_chunks hits the SQLite fallback engine
        # and fails on the pgvector operator → retrieval degrades to no context.
        resp = _client().post("/chat", json={"messages": [{"role": "user", "content": "hi"}]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["sources"] == []


class TestChatStream:
    def test_stream_emits_sse_frames(self, ai_enabled):
        """stream=true returns SSE meta/token/done frames (#1131)."""

        async def fake_stream(**kwargs):
            yield "Hello"
            yield " world"

        ai_enabled.llm.generate_stream = fake_stream

        resp = _client().post(
            "/chat",
            json={"messages": [{"role": "user", "content": "hi"}], "stream": True},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        body = resp.text
        assert "event: meta" in body
        assert '"sources"' in body
        assert 'event: token\ndata: {"text": "Hello"}' in body
        assert 'event: token\ndata: {"text": " world"}' in body
        assert "event: done" in body

    def test_stream_falls_back_to_generate_when_no_stream_support(self, ai_enabled):
        """Clients without generate_stream still yield their full reply as a
        single token frame (#1131)."""
        resp = _client().post(
            "/chat",
            json={"messages": [{"role": "user", "content": "hi"}], "stream": True},
        )
        assert resp.status_code == 200
        assert 'event: token\ndata: {"text": "llm answer"}' in resp.text

    def test_stream_circuit_open_emits_error_frame(self, ai_enabled):
        main.llm_circuit_breaker.state = CircuitState.OPEN
        main.llm_circuit_breaker.last_failure_time = time.time()
        resp = _client().post(
            "/chat",
            json={"messages": [{"role": "user", "content": "hi"}], "stream": True},
        )
        assert resp.status_code == 200
        assert "event: error" in resp.text
        assert "circuit_open" in resp.text

    def test_non_stream_unaffected_by_stream_flag_default(self, ai_enabled):
        """Default stream=false keeps the JSON response contract."""
        resp = _client().post("/chat", json={"messages": [{"role": "user", "content": "hi"}]})
        assert resp.headers["content-type"].startswith("application/json")
        assert resp.json()["response"] == "llm answer"


# ── sync DB calls offloaded from the event loop (#1533) ──────────────────


class TestSyncDbOffloaded(unittest.IsolatedAsyncioTestCase):
    """#1533: psycopg2 calls inside async handlers must run via
    ``asyncio.to_thread`` — never on the event-loop thread itself."""

    def _fake_embedding_client(self):
        return SimpleNamespace(
            provider_name="fake-emb",
            embed=AsyncMock(return_value=[0.1, 0.2, 0.3]),
        )

    async def test_retrieve_note_context_returns_chunks(self):
        """Refactor correctness (#1541): the single JOINed similarity query
        still yields the same ``note_id``/``title``/``snippet`` payload, and
        the caller caps it at MAX_CONTEXT_NOTES with the snippet length."""
        captured: dict = {}

        def fake_find(vec, limit, snippet_chars):
            captured["limit"] = limit
            captured["snippet_chars"] = snippet_chars
            return [
                {"note_id": 1, "title": "First", "snippet": "body one"},
                {"note_id": 3, "title": "Third", "snippet": "body three"},
            ]

        with (
            patch.object(main, "get_embedding_client", return_value=self._fake_embedding_client()),
            patch.object(database, "find_similar_note_chunks", fake_find),
        ):
            chunks = await main._retrieve_note_context("question", top_k=10)

        assert chunks == [
            {"note_id": 1, "title": "First", "snippet": "body one"},
            {"note_id": 3, "title": "Third", "snippet": "body three"},
        ]
        assert captured["limit"] == main.MAX_CONTEXT_NOTES
        assert captured["snippet_chars"] == main.MAX_NOTE_CHARS

    async def test_retrieve_note_context_top_k_below_cap_passes_through(self):
        """top_k below MAX_CONTEXT_NOTES is forwarded as the query limit."""
        captured: dict = {}

        def fake_find(vec, limit, snippet_chars):
            captured["limit"] = limit
            return []

        with (
            patch.object(main, "get_embedding_client", return_value=self._fake_embedding_client()),
            patch.object(database, "find_similar_note_chunks", fake_find),
        ):
            assert await main._retrieve_note_context("q", top_k=3) == []

        assert captured["limit"] == 3

    async def test_find_similar_notes_runs_in_worker_thread(self):
        """The pgvector lookup executes on a thread-pool thread, not on the
        event-loop thread."""
        loop_thread = threading.get_ident()
        db_threads: list[int] = []

        def fake_find(vec, limit, snippet_chars):
            db_threads.append(threading.get_ident())
            return []

        with (
            patch.object(main, "get_embedding_client", return_value=self._fake_embedding_client()),
            patch.object(database, "find_similar_note_chunks", fake_find),
        ):
            chunks = await main._retrieve_note_context("q")

        assert chunks == []
        assert db_threads and all(t != loop_thread for t in db_threads)

    async def test_blocking_db_call_does_not_stall_event_loop(self):
        """A blocking psycopg2 call must not freeze the event loop — other
        coroutines keep ticking while it waits (#1533)."""
        entered = threading.Event()
        release = threading.Event()
        heartbeats = 0

        def slow_find(vec, limit, snippet_chars):
            entered.set()
            release.wait(timeout=10)
            return []

        async def heartbeat():
            nonlocal heartbeats
            while not release.is_set():
                heartbeats += 1
                await asyncio.sleep(0.01)

        async def scenario():
            task = asyncio.create_task(main._retrieve_note_context("q"))
            hb = asyncio.create_task(heartbeat())
            # Wait until the DB call is genuinely in flight, then wait for
            # the loop to tick at least once while it stays blocked — no
            # fixed window or tick threshold, so loaded CI runners cannot
            # flake this (#1584).
            while not entered.is_set():
                await asyncio.sleep(0.005)
            observed = heartbeats
            while heartbeats == observed:
                await asyncio.sleep(0.01)
            release.set()
            await asyncio.gather(task, hb)

        with (
            patch.object(main, "get_embedding_client", return_value=self._fake_embedding_client()),
            patch.object(database, "find_similar_note_chunks", slow_find),
        ):
            # Bounded: if the sync call ran on the loop, the loop would freeze
            # inside release.wait() and this would time out instead.
            await asyncio.wait_for(scenario(), timeout=10)

        assert heartbeats >= 1


# ── batched DB access (#1541) ──────────────────────────────────────────


def _mock_engine_fetchall(monkeypatch, rows):
    """Point ``database.engine`` at a fake connection whose every execute()
    returns ``rows`` from fetchall(); returns the conn mock for assertions."""
    engine = MagicMock()
    conn = engine.connect.return_value.__enter__.return_value
    conn.execute.return_value.fetchall.return_value = rows
    monkeypatch.setattr(database, "engine", engine)
    return conn


class TestSimilarNoteChunksQuery:
    def test_single_joined_query(self, monkeypatch):
        """#1541: similarity + title/snippet fetch happen in ONE JOINed query —
        not a similarity lookup plus a per-id SELECT."""
        conn = _mock_engine_fetchall(
            monkeypatch,
            [(7, "My Note", "snippet text"), (9, "Other", "more")],
        )

        chunks = database.find_similar_note_chunks([0.1, 0.2], limit=5, snippet_chars=2000)

        conn.execute.assert_called_once()
        sql = str(conn.execute.call_args.args[0])
        assert "JOIN notes" in sql
        assert "ORDER BY" in sql
        params = conn.execute.call_args.args[1]
        assert params["limit"] == 5
        assert params["snippet_chars"] == 2000
        assert chunks == [
            {"note_id": 7, "title": "My Note", "snippet": "snippet text"},
            {"note_id": 9, "title": "Other", "snippet": "more"},
        ]

    def test_null_snippet_becomes_empty_string(self, monkeypatch):
        """left(content, n) is NULL for NULL content — callers expect ''."""
        _mock_engine_fetchall(monkeypatch, [(7, "T", None)])
        assert database.find_similar_note_chunks([0.1], limit=5, snippet_chars=2000) == [
            {"note_id": 7, "title": "T", "snippet": ""}
        ]


class TestClusterBatching:
    def test_single_in_query_for_all_clusters(self, monkeypatch):
        """#1541: titles for every cluster are fetched with one IN query,
        preserving per-cluster id order and 'Unknown' for missing notes."""
        conn = _mock_engine_fetchall(
            monkeypatch,
            [(1, "Alpha"), (3, "Gamma"), (4, "Delta")],  # note 2 missing
        )
        clusters = {0: [1, 2, 3], 5: [4]}

        results = main._build_cluster_results(clusters)

        conn.execute.assert_called_once()
        assert results == [
            {
                "cluster_id": 0,
                "note_ids": [1, 2, 3],
                "note_count": 3,
                "representative_title": "Alpha",
                "titles": ["Alpha", "Unknown", "Gamma"],
            },
            {
                "cluster_id": 5,
                "note_ids": [4],
                "note_count": 1,
                "representative_title": "Delta",
                "titles": ["Delta"],
            },
        ]

    def test_empty_clusters_skip_query(self, monkeypatch):
        conn = _mock_engine_fetchall(monkeypatch, [])
        assert main._build_cluster_results({}) == []
        conn.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
