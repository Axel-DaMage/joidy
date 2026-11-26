"""Tests for AI provider fallback behavior (#568, #1460).

Verifies that:
1. FallbackLLMClient tries primary, then each fallback in order on exception
2. FallbackEmbeddingClient tries primary, falls back to secondary on exception
3. ClientFactory builds the full configured-provider chain (Ollama last)
4. ClientFactory does NOT wrap when only the primary is configured
5. health_check() returns True if any chain member is healthy
6. health_check() returns False if every provider is unreachable
"""

import time
import unittest
from unittest.mock import patch

from clients.base import BaseLLMClient, EmbeddingClient
from clients.factory import ClientFactory
from clients.fallback import FallbackEmbeddingClient, FallbackLLMClient


class FakeLLMClient(BaseLLMClient):
    """Fake LLM client for testing — configurable to succeed or fail."""

    def __init__(self, name: str, fail: bool = False, embed_fail: bool = False):
        self._name = name
        self._fail = fail
        self._embed_fail = embed_fail or fail
        self.generate_calls = 0
        self.embed_calls = 0
        self.health_check_calls = 0

    @property
    def provider_name(self) -> str:
        return self._name

    async def embed_text(self, text: str) -> list[float]:
        self.embed_calls += 1
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
        self.generate_calls += 1
        if self._fail:
            raise Exception(f"{self._name} generate failed")
        return f"{self._name}:response"

    async def health_check(self) -> bool:
        self.health_check_calls += 1
        return not self._fail


class FakeEmbeddingClient(EmbeddingClient):
    """Fake embedding client for testing."""

    def __init__(self, name: str, fail: bool = False):
        self._name = name
        self._fail = fail
        self.embed_calls = 0
        self.health_check_calls = 0

    @property
    def provider_name(self) -> str:
        return self._name

    async def embed(self, text: str) -> list[float]:
        self.embed_calls += 1
        if self._fail:
            raise Exception(f"{self._name} embed failed")
        return [0.4, 0.5, 0.6]

    async def health_check(self) -> bool:
        self.health_check_calls += 1
        return not self._fail


class TestFallbackLLMClient(unittest.IsolatedAsyncioTestCase):
    """Tests for FallbackLLMClient."""

    async def test_primary_succeeds_no_fallback(self):
        primary = FakeLLMClient("gemini", fail=False)
        secondary = FakeLLMClient("ollama", fail=False)
        client = FallbackLLMClient(primary=primary, fallbacks=[secondary])

        result = await client.generate("test")
        self.assertEqual(result, "gemini:response")
        self.assertEqual(client.provider_name, "gemini")

    async def test_primary_fails_fallback_to_secondary(self):
        primary = FakeLLMClient("gemini", fail=True)
        secondary = FakeLLMClient("ollama", fail=False)
        client = FallbackLLMClient(primary=primary, fallbacks=[secondary])

        result = await client.generate("test")
        self.assertEqual(result, "ollama:response")
        self.assertEqual(client.provider_name, "ollama")

    async def test_both_fail_raises_exception(self):
        primary = FakeLLMClient("gemini", fail=True)
        secondary = FakeLLMClient("ollama", fail=True)
        client = FallbackLLMClient(primary=primary, fallbacks=[secondary])

        with self.assertRaises(Exception):  # noqa: B017 -- fallback must swallow any provider error type
            await client.generate("test")

    async def test_embed_text_primary_succeeds(self):
        primary = FakeLLMClient("gemini", fail=False)
        secondary = FakeLLMClient("ollama", fail=False)
        client = FallbackLLMClient(primary=primary, fallbacks=[secondary])

        result = await client.embed_text("test")
        self.assertEqual(result, [0.1, 0.2, 0.3])

    async def test_embed_text_falls_back(self):
        primary = FakeLLMClient("gemini", fail=False, embed_fail=True)
        secondary = FakeLLMClient("ollama", fail=False)
        client = FallbackLLMClient(primary=primary, fallbacks=[secondary])

        result = await client.embed_text("test")
        self.assertEqual(result, [0.1, 0.2, 0.3])
        self.assertEqual(client.provider_name, "ollama")

    async def test_health_check_primary_healthy(self):
        primary = FakeLLMClient("gemini", fail=False)
        secondary = FakeLLMClient("ollama", fail=False)
        client = FallbackLLMClient(primary=primary, fallbacks=[secondary])

        result = await client.health_check()
        self.assertTrue(result)
        self.assertEqual(client.provider_name, "gemini")

    async def test_health_check_primary_down_secondary_healthy(self):
        primary = FakeLLMClient("gemini", fail=True)
        secondary = FakeLLMClient("ollama", fail=False)
        client = FallbackLLMClient(primary=primary, fallbacks=[secondary])

        result = await client.health_check()
        self.assertTrue(result)
        self.assertEqual(client.provider_name, "ollama")

    async def test_health_check_both_down(self):
        primary = FakeLLMClient("gemini", fail=True)
        secondary = FakeLLMClient("ollama", fail=True)
        client = FallbackLLMClient(primary=primary, fallbacks=[secondary])

        result = await client.health_check()
        self.assertFalse(result)

    # ── Multi-provider chain (#1460) ────────────────────────────────────

    async def test_chain_property_lists_all_providers_in_order(self):
        primary = FakeLLMClient("openai")
        fb1 = FakeLLMClient("gemini")
        fb2 = FakeLLMClient("ollama")
        client = FallbackLLMClient(primary=primary, fallbacks=[fb1, fb2])

        self.assertEqual([c.provider_name for c in client.chain], ["openai", "gemini", "ollama"])

    async def test_falls_through_multiple_providers(self):
        """primary → gemini → ollama: two failures land on the third."""
        client = FallbackLLMClient(
            primary=FakeLLMClient("openai", fail=True),
            fallbacks=[FakeLLMClient("gemini", fail=True), FakeLLMClient("ollama")],
        )

        result = await client.generate("test")
        self.assertEqual(result, "ollama:response")
        self.assertEqual(client.provider_name, "ollama")

    async def test_middle_fallback_wins_over_later_ones(self):
        client = FallbackLLMClient(
            primary=FakeLLMClient("openai", fail=True),
            fallbacks=[FakeLLMClient("gemini"), FakeLLMClient("ollama")],
        )

        result = await client.generate("test")
        self.assertEqual(result, "gemini:response")
        self.assertEqual(client.provider_name, "gemini")

    async def test_all_providers_down_raises_last_error(self):
        client = FallbackLLMClient(
            primary=FakeLLMClient("openai", fail=True),
            fallbacks=[FakeLLMClient("gemini", fail=True), FakeLLMClient("ollama", fail=True)],
        )

        with self.assertRaises(Exception) as ctx:  # noqa: B017 -- fallback must swallow any provider error type
            await client.generate("test")
        # The LAST provider's error surfaces — first in the chain is not
        # hidden behind a generic "primary failed" (#1460).
        self.assertIn("ollama generate failed", str(ctx.exception))

    async def test_health_check_reports_first_healthy_provider(self):
        client = FallbackLLMClient(
            primary=FakeLLMClient("openai", fail=True),
            fallbacks=[FakeLLMClient("gemini"), FakeLLMClient("ollama")],
        )

        self.assertTrue(await client.health_check())
        self.assertEqual(client.provider_name, "gemini")

    async def test_embed_text_falls_through_chain(self):
        client = FallbackLLMClient(
            primary=FakeLLMClient("openai", embed_fail=True),
            fallbacks=[FakeLLMClient("gemini", embed_fail=True), FakeLLMClient("ollama")],
        )

        result = await client.embed_text("test")
        self.assertEqual(result, [0.1, 0.2, 0.3])
        self.assertEqual(client.provider_name, "ollama")


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

        with self.assertRaises(Exception):  # noqa: B017 -- fallback must swallow any provider error type
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


class TestFallbackLLMStickiness(unittest.IsolatedAsyncioTestCase):
    """Sticky failover (#1538): a failed provider is skipped during its
    cooldown so traffic goes straight to the healthy fallback, then retried
    (half-open) once the cooldown expires."""

    async def test_failed_primary_skipped_during_cooldown(self):
        primary = FakeLLMClient("gemini", fail=True)
        secondary = FakeLLMClient("ollama", fail=False)
        client = FallbackLLMClient(primary=primary, fallbacks=[secondary])

        self.assertEqual(await client.generate("one"), "ollama:response")
        self.assertEqual(await client.generate("two"), "ollama:response")
        self.assertEqual(await client.generate("three"), "ollama:response")
        # The dead primary paid its failure latency exactly ONCE; subsequent
        # requests went straight to the fallback.
        self.assertEqual(primary.generate_calls, 1)
        self.assertEqual(secondary.generate_calls, 3)
        self.assertEqual(client.provider_name, "ollama")

    async def test_failed_primary_skipped_for_embed_text(self):
        primary = FakeLLMClient("gemini", embed_fail=True)
        secondary = FakeLLMClient("ollama")
        client = FallbackLLMClient(primary=primary, fallbacks=[secondary])

        await client.embed_text("one")
        await client.embed_text("two")
        self.assertEqual(primary.embed_calls, 1)
        self.assertEqual(secondary.embed_calls, 2)

    async def test_primary_retried_after_cooldown_expires(self):
        """Half-open probe: once the cooldown expires the primary is tried
        again in its normal position; a success clears the cooldown."""
        primary = FakeLLMClient("gemini", fail=True)
        secondary = FakeLLMClient("ollama")
        client = FallbackLLMClient(primary=primary, fallbacks=[secondary])

        await client.generate("one")
        self.assertEqual(primary.generate_calls, 1)

        # Cooldown expires → next request probes the primary again.
        client._down_until[0] = 0.0
        primary._fail = False
        self.assertEqual(await client.generate("two"), "gemini:response")
        self.assertEqual(primary.generate_calls, 2)
        self.assertEqual(client.provider_name, "gemini")
        self.assertEqual(client._down_until, {})

    async def test_still_failing_primary_rearms_cooldown(self):
        primary = FakeLLMClient("gemini", fail=True)
        secondary = FakeLLMClient("ollama")
        client = FallbackLLMClient(primary=primary, fallbacks=[secondary])

        await client.generate("one")
        self.assertEqual(primary.generate_calls, 1)

        # Cooldown expires but the primary still fails → re-cooled and
        # skipped again on the following request.
        client._down_until[0] = 0.0
        await client.generate("two")
        self.assertEqual(primary.generate_calls, 2)
        await client.generate("three")
        self.assertEqual(primary.generate_calls, 2)
        self.assertEqual(secondary.generate_calls, 3)

    async def test_all_providers_cooling_still_tries_chain(self):
        """When every provider is in cooldown the full chain is still tried —
        degraded latency beats a certain error."""
        primary = FakeLLMClient("gemini")
        secondary = FakeLLMClient("ollama")
        client = FallbackLLMClient(primary=primary, fallbacks=[secondary])
        future = time.monotonic() + 3600
        client._down_until = {0: future, 1: future}

        self.assertEqual(await client.generate("x"), "gemini:response")
        self.assertEqual(primary.generate_calls, 1)
        # Success cleared the primary's cooldown entry.
        self.assertNotIn(0, client._down_until)

    async def test_health_check_skips_cooling_provider(self):
        primary = FakeLLMClient("gemini", fail=True)
        secondary = FakeLLMClient("ollama")
        client = FallbackLLMClient(primary=primary, fallbacks=[secondary])
        client._down_until = {0: time.monotonic() + 3600}

        self.assertTrue(await client.health_check())
        # Known-down primary was not pinged — no wasted billable probe.
        self.assertEqual(primary.health_check_calls, 0)
        self.assertEqual(client.provider_name, "ollama")


class TestFallbackEmbeddingStickiness(unittest.IsolatedAsyncioTestCase):
    """Same cooldown stickiness for the two-provider embedding chain (#1538)."""

    async def test_failed_primary_skipped_during_cooldown(self):
        primary = FakeEmbeddingClient("gemini", fail=True)
        secondary = FakeEmbeddingClient("ollama")
        client = FallbackEmbeddingClient(primary=primary, secondary=secondary)

        await client.embed("one")
        await client.embed("two")
        self.assertEqual(primary.embed_calls, 1)
        self.assertEqual(secondary.embed_calls, 2)
        self.assertEqual(client.provider_name, "ollama")

    async def test_primary_retried_after_cooldown_expires(self):
        primary = FakeEmbeddingClient("gemini", fail=True)
        secondary = FakeEmbeddingClient("ollama")
        client = FallbackEmbeddingClient(primary=primary, secondary=secondary)

        await client.embed("one")
        self.assertEqual(primary.embed_calls, 1)

        client._primary_down_until = 0.0
        primary._fail = False
        await client.embed("two")
        self.assertEqual(primary.embed_calls, 2)
        self.assertEqual(client.provider_name, "gemini")

    async def test_health_check_skips_cooling_primary(self):
        primary = FakeEmbeddingClient("gemini", fail=True)
        secondary = FakeEmbeddingClient("ollama")
        client = FallbackEmbeddingClient(primary=primary, secondary=secondary)
        client._primary_down_until = time.monotonic() + 3600

        self.assertTrue(await client.health_check())
        self.assertEqual(primary.health_check_calls, 0)


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

    # ── Multi-provider chain order (#1460) ────────────────────────────────

    @patch("clients.factory.settings")
    def test_factory_llm_chain_uses_all_configured_providers(self, mock_settings):
        """Chain: LLM_MODEL provider first, then other configured providers in
        canonical order, Ollama last."""
        mock_settings.llm_model = "openai:standardcompute"
        mock_settings.available_providers = ["openai", "gemini", "ollama"]
        mock_settings.provider_config = {
            "openai": {"api_key": "fake-openai", "base_url": "https://router.example.com/v1"},
            "gemini": {"api_key": "fake-gemini"},
            "ollama": {"base_url": "http://localhost:11434"},
        }

        client = ClientFactory.get_llm_client()
        self.assertIsInstance(client, FallbackLLMClient)
        self.assertEqual([c.provider_name for c in client.chain], ["openai", "gemini", "ollama"])

    @patch("clients.factory.settings")
    def test_factory_llm_chain_prefers_configured_provider_over_ollama(self, mock_settings):
        """A configured Gemini key must be tried before Ollama — the old
        primary→ollama chain ignored it entirely (#1460)."""
        mock_settings.llm_model = "anthropic:claude-3-haiku"
        mock_settings.available_providers = ["anthropic", "gemini", "ollama"]
        mock_settings.provider_config = {
            "anthropic": {"api_key": "fake-anthropic"},
            "gemini": {"api_key": "fake-gemini"},
            "ollama": {"base_url": "http://localhost:11434"},
        }

        client = ClientFactory.get_llm_client()
        names = [c.provider_name for c in client.chain]
        self.assertEqual(names, ["anthropic", "gemini", "ollama"])

    @patch("clients.factory.settings")
    def test_factory_llm_chain_ollama_primary_not_duplicated(self, mock_settings):
        """Ollama as primary must not appear twice in its own chain."""
        mock_settings.llm_model = "ollama:llama3"
        mock_settings.available_providers = ["gemini", "ollama"]
        mock_settings.provider_config = {
            "gemini": {"api_key": "fake-gemini"},
            "ollama": {"base_url": "http://localhost:11434"},
        }

        client = ClientFactory.get_llm_client()
        names = [c.provider_name for c in client.chain]
        self.assertEqual(names, ["ollama", "gemini"])
        self.assertEqual(names.count("ollama"), 1)

    @patch("clients.factory.settings")
    def test_factory_llm_no_chain_when_only_primary_configured(self, mock_settings):
        mock_settings.llm_model = "openai:gpt-4o-mini"
        mock_settings.available_providers = ["openai"]
        mock_settings.provider_config = {"openai": {"api_key": "fake"}}

        client = ClientFactory.get_llm_client()
        self.assertNotIsInstance(client, FallbackLLMClient)
        self.assertEqual(client.provider_name, "openai")


if __name__ == "__main__":
    unittest.main()
