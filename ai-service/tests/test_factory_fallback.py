"""Tests for ClientFactory provider fallback logic (#568)."""

from unittest.mock import patch

import pytest

from clients.factory import ClientFactory


@pytest.fixture(autouse=True)
def _reset_factory():
    """Ensure cached clients don't leak between tests."""
    ClientFactory.reset()
    yield
    ClientFactory.reset()


def _mock_settings(available_configs: dict, llm_model="gemini:gemini-2.0-flash", embedding_model="gemini:models/text-embedding-004"):
    """Build a mock settings object with the given provider configs."""
    class FakeSettings:
        def __init__(self):
            self.llm_model = llm_model
            self.embedding_model = embedding_model

        @property
        def provider_config(self):
            return available_configs

        @property
        def available_providers(self):
            return list(available_configs.keys())

        @property
        def is_ai_enabled(self):
            return len(available_configs) > 0

    return FakeSettings()


def test_fallback_to_ollama_when_gemini_unavailable():
    """If Gemini is configured but not available, fall back to Ollama (#568)."""
    fake = _mock_settings({
        "ollama": {"base_url": "http://localhost:11434"},
    })
    with patch("clients.factory.settings", fake):
        client = ClientFactory.get_llm_client()
        assert client.provider_name == "ollama"
        active = ClientFactory.get_active_providers()
        assert active["llm"]["provider"] == "ollama"
        assert active["llm"]["model"] == "llama3"


def test_fallback_embedding_to_ollama():
    """Embedding client falls back to Ollama with nomic-embed-text."""
    fake = _mock_settings({
        "ollama": {"base_url": "http://localhost:11434"},
    })
    with patch("clients.factory.settings", fake):
        client = ClientFactory.get_embedding_client()
        assert client.provider_name == "ollama"
        active = ClientFactory.get_active_providers()
        assert active["embedding"]["provider"] == "ollama"
        assert active["embedding"]["model"] == "nomic-embed-text"


def test_no_fallback_when_provider_available():
    """If the configured provider is available, no fallback occurs."""
    fake = _mock_settings({
        "gemini": {"api_key": "test-key"},
    })
    with patch("clients.factory.settings", fake):
        client = ClientFactory.get_llm_client()
        assert client.provider_name == "gemini"
        active = ClientFactory.get_active_providers()
        assert active["llm"]["provider"] == "gemini"
        assert active["llm"]["model"] == "gemini-2.0-flash"


def test_no_provider_available_raises():
    """If no provider is available at all, ValueError is raised."""
    fake = _mock_settings({})
    with patch("clients.factory.settings", fake):
        with pytest.raises(ValueError, match="No llm provider available"):
            ClientFactory.get_llm_client()


def test_fallback_skips_no_embedding_providers():
    """Anthropic/OpenRouter are skipped for embedding fallback."""
    fake = _mock_settings({
        "anthropic": {"api_key": "test-key"},
    })
    with patch("clients.factory.settings", fake):
        with pytest.raises(ValueError, match="No embedding provider available"):
            ClientFactory.get_embedding_client()


def test_embedding_fallback_from_anthropic_configured():
    """If anthropic is configured for embeddings, fall back to an embedding-capable provider."""
    fake = _mock_settings(
        {
            "anthropic": {"api_key": "test-key"},
            "ollama": {"base_url": "http://localhost:11434"},
        },
        embedding_model="anthropic:claude-3-5-sonnet-20241022",
    )
    with patch("clients.factory.settings", fake):
        client = ClientFactory.get_embedding_client()
        assert client.provider_name == "ollama"
        active = ClientFactory.get_active_providers()
        assert active["embedding"]["provider"] == "ollama"


def test_fallback_prefers_ollama_over_openai():
    """When multiple providers available, Ollama is preferred (local/free)."""
    fake = _mock_settings({
        "openai": {"api_key": "test-key"},
        "ollama": {"base_url": "http://localhost:11434"},
    })
    with patch("clients.factory.settings", fake):
        client = ClientFactory.get_llm_client()
        assert client.provider_name == "ollama"
