"""Tests for AI provider fallback behavior (#568).

Verifies that:
1. FallbackLLMClient tries primary, falls back to secondary on exception
2. FallbackEmbeddingClient tries primary, falls back to secondary on exception
3. ClientFactory wraps primary with Ollama fallback when Ollama is available
4. ClientFactory does NOT wrap when primary is already Ollama
5. health_check() returns True if either primary or secondary is healthy
6. health_check() returns False if both providers are unreachable
"""

import asyncio
import unittest
from unittest.mock import MagicMock, patch

from clients.base import BaseLLMClient, EmbeddingClient
from clients.factory import ClientFactory
from clients.fallback import FallbackEmbeddingClient, FallbackLLMClient


class FakeLLMClient(BaseLLMClient):
    """Fake LLM client for testing — configurable to succeed or fail."""

    def __init__(self, name: str, fail: bool = False, embed_fail: bool = False):
        self._name = name
        self._fail = fail
        self._embed_fail = embed_fail or fail

    @property
    def provider_name(self) -> str:
        return self._name

    async def embed_text(self, text: str) -> list[float]:
        if self._embed_fail:
            raise Exception(f"{self._name} embed_text failed")
        return [0.1, 0.2, 0.3]

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 256,
        system_prompt: str | None = None,
    ) -> str:
        if self._fail:
            raise Exception(f"{self._name} generate failed")
        return f"{self._name}:response"

    async def health_check(self) -> bool:
        return not self._fail


class FakeEmbeddingClient(EmbeddingClient):
    """Fake embedding client for testing."""

    def __init__(self, name: str, fail: bool = False):
        self._name = name
        self._fail = fail

    @property
    def provider_name(self) -> str:
        return self._name

    async def embed(self, text: str) -> list[float]:
        if self._fail:
            raise Exception(f"{self._name} embed failed")
        return [0.4, 0.5, 0.6]

    async def health_check(self) -> bool:
        return not self._fail


class TestFallbackLLMClient(unittest.IsolatedAsyncioTestCase):
    """Tests for FallbackLLMClient."""

    async def test_primary_succeeds_no_fallback(self):
        primary = FakeLLMClient("gemini", fail=False)
        secondary = FakeLLMClient("ollama", fail=False)
        client = FallbackLLMClient(primary=primary, secondary=secondary)

        result = await client.generate("test")
        self.assertEqual(result, "gemini:response")
        self.assertEqual(client.provider_name, "gemini")

    async def test_primary_fails_fallback_to_secondary(self):
        primary = FakeLLMClient("gemini", fail=True)
        secondary = FakeLLMClient("ollama", fail=False)
        client = FallbackLLMClient(primary=primary, secondary=secondary)

        result = await client.generate("test")
        self.assertEqual(result, "ollama:response")
        self.assertEqual(client.provider_name, "ollama")

    async def test_both_fail_raises_exception(self):
        primary = FakeLLMClient("gemini", fail=True)
        secondary = FakeLLMClient("ollama", fail=True)
        client = FallbackLLMClient(primary=primary, secondary=secondary)

        with self.assertRaises(Exception):
            await client.generate("test")

    async def test_embed_text_primary_succeeds(self):
        primary = FakeLLMClient("gemini", fail=False)
        secondary = FakeLLMClient("ollama", fail=False)
        client = FallbackLLMClient(primary=primary, secondary=secondary)

        result = await client.embed_text("test")
        self.assertEqual(result, [0.1, 0.2, 0.3])

    async def test_embed_text_falls_back(self):
        primary = FakeLLMClient("gemini", fail=False, embed_fail=True)
        secondary = FakeLLMClient("ollama", fail=False)
        client = FallbackLLMClient(primary=primary, secondary=secondary)

        result = await client.embed_text("test")
        self.assertEqual(result, [0.1, 0.2, 0.3])
        self.assertEqual(client.provider_name, "ollama")

    async def test_health_check_primary_healthy(self):
        primary = FakeLLMClient("gemini", fail=False)
        secondary = FakeLLMClient("ollama", fail=False)
        client = FallbackLLMClient(primary=primary, secondary=secondary)

        result = await client.health_check()
        self.assertTrue(result)
        self.assertEqual(client.provider_name, "gemini")

    async def test_health_check_primary_down_secondary_healthy(self):
        primary = FakeLLMClient("gemini", fail=True)
        secondary = FakeLLMClient("ollama", fail=False)
        client = FallbackLLMClient(primary=primary, secondary=secondary)

        result = await client.health_check()
        self.assertTrue(result)
        self.assertEqual(client.provider_name, "ollama")

    async def test_health_check_both_down(self):
        primary = FakeLLMClient("gemini", fail=True)
        secondary = FakeLLMClient("ollama", fail=True)
        client = FallbackLLMClient(primary=primary, secondary=secondary)

        result = await client.health_check()
        self.assertFalse(result)


class TestFallbackEmbeddingClient(unittest.IsolatedAsyncioTestCase):
    """Tests for FallbackEmbeddingClient."""

    async def test_primary_succeeds_no_fallback(self):
        primary = FakeEmbeddingClient("gemini", fail=False)
        secondary = FakeEmbeddingClient("ollama", fail=False)
        client = FallbackEmbeddingClient(primary=primary, secondary=secondary)

        result = await client.embed("test")
        self.assertEqual(result, [0.4, 0.5, 0.6])
        self.assertEqual(client.provider_name, "gemini")

    async def test_primary_fails_fallback_to_secondary(self):
        primary = FakeEmbeddingClient("gemini", fail=True)
        secondary = FakeEmbeddingClient("ollama", fail=False)
        client = FallbackEmbeddingClient(primary=primary, secondary=secondary)

        result = await client.embed("test")
        self.assertEqual(result, [0.4, 0.5, 0.6])
        self.assertEqual(client.provider_name, "ollama")

    async def test_both_fail_raises_exception(self):
        primary = FakeEmbeddingClient("gemini", fail=True)
        secondary = FakeEmbeddingClient("ollama", fail=True)
        client = FallbackEmbeddingClient(primary=primary, secondary=secondary)

        with self.assertRaises(Exception):
            await client.embed("test")

    async def test_health_check_primary_healthy(self):
        primary = FakeEmbeddingClient("gemini", fail=False)
        secondary = FakeEmbeddingClient("ollama", fail=False)
        client = FallbackEmbeddingClient(primary=primary, secondary=secondary)

        result = await client.health_check()
        self.assertTrue(result)

    async def test_health_check_both_down(self):
        primary = FakeEmbeddingClient("gemini", fail=True)
        secondary = FakeEmbeddingClient("ollama", fail=True)
        client = FallbackEmbeddingClient(primary=primary, secondary=secondary)

        result = await client.health_check()
        self.assertFalse(result)


class TestClientFactoryFallback(unittest.IsolatedAsyncioTestCase):
    """Tests for ClientFactory fallback wrapping."""

    def setUp(self):
        ClientFactory.reset()

    def tearDown(self):
        ClientFactory.reset()

    @patch("clients.factory.settings")
    def test_factory_wraps_with_fallback_when_ollama_available(self, mock_settings):
        """Factory should wrap primary with FallbackLLMClient when Ollama is available."""
        mock_settings.llm_model = "gemini:gemini-2.0-flash"
        mock_settings.available_providers = ["gemini", "ollama"]
        mock_settings.provider_config = {
            "gemini": {"api_key": "fake-key"},
            "ollama": {"base_url": "http://localhost:11434"},
        }

        client = ClientFactory.get_llm_client()
        self.assertIsInstance(client, FallbackLLMClient)

    @patch("clients.factory.settings")
    def test_factory_no_fallback_when_ollama_not_available(self, mock_settings):
        """Factory should NOT wrap when Ollama is not available."""
        mock_settings.llm_model = "gemini:gemini-2.0-flash"
        mock_settings.available_providers = ["gemini"]
        mock_settings.provider_config = {
            "gemini": {"api_key": "fake-key"},
        }

        client = ClientFactory.get_llm_client()
        self.assertNotIsInstance(client, FallbackLLMClient)
        self.assertEqual(client.provider_name, "gemini")

    @patch("clients.factory.settings")
    def test_factory_no_fallback_when_primary_is_ollama(self, mock_settings):
        """Factory should NOT wrap when primary provider is already Ollama."""
        mock_settings.llm_model = "ollama:llama3"
        mock_settings.available_providers = ["ollama"]
        mock_settings.provider_config = {
            "ollama": {"base_url": "http://localhost:11434"},
        }

        client = ClientFactory.get_llm_client()
        self.assertNotIsInstance(client, FallbackLLMClient)
        self.assertEqual(client.provider_name, "ollama")

    @patch("clients.factory.settings")
    def test_factory_wraps_embedding_with_fallback(self, mock_settings):
        """Factory should wrap embedding client with fallback when Ollama is available."""
        mock_settings.embedding_model = "gemini:models/text-embedding-004"
        mock_settings.available_providers = ["gemini", "ollama"]
        mock_settings.provider_config = {
            "gemini": {"api_key": "fake-key"},
            "ollama": {"base_url": "http://localhost:11434"},
        }

        client = ClientFactory.get_embedding_client()
        self.assertIsInstance(client, FallbackEmbeddingClient)

    @patch("clients.factory.settings")
    def test_factory_no_embedding_fallback_when_ollama_unavailable(self, mock_settings):
        """Factory should NOT wrap embedding when Ollama is not available."""
        mock_settings.embedding_model = "gemini:models/text-embedding-004"
        mock_settings.available_providers = ["gemini"]
        mock_settings.provider_config = {
            "gemini": {"api_key": "fake-key"},
        }

        client = ClientFactory.get_embedding_client()
        self.assertNotIsInstance(client, FallbackEmbeddingClient)


if __name__ == "__main__":
    unittest.main()
