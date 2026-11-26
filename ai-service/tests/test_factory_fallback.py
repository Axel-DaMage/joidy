"""Tests for AI provider fallback behavior (#568, #1460).

Verifies that:
1. FallbackLLMClient tries primary, then each fallback in order on exception
2. FallbackEmbeddingClient tries primary, falls back to secondary on exception
3. ClientFactory builds the full configured-provider chain (Ollama last)
4. ClientFactory does NOT wrap when only the primary is configured
5. health_check() returns True if any chain member is healthy
6. health_check() returns False if every provider is unreachable
"""

import asyncio
import time
import unittest
from unittest.mock import patch

from clients.base import BaseLLMClient, EmbeddingClient
from clients.factory import ClientFactory
from clients.fallback import FallbackEmbeddingClient, FallbackLLMClient, _is_health_error


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


class _StatusError(Exception):
    """Exception carrying a typed HTTP status (OpenAI/Anthropic style)."""

    def __init__(self, status_code: int):
        super().__init__(f"request failed with status {status_code}")
        self.status_code = status_code


class _StatusInMessageClient(FakeLLMClient):
    """Provider that only stringifies the status in the error message
    (Ollama-style: ``... failed (HTTP 503): <body>``)."""

    def __init__(self, name: str, status: int):
        super().__init__(name)
        self._status = status

    async def generate(self, prompt, temperature=0.2, max_tokens=256, system_prompt=None) -> str:
        self.generate_calls += 1
        raise Exception(f"{self._name} generate failed (HTTP {self._status}): boom")


class TestIsHealthError(unittest.TestCase):
    """#1628: only transient/provider-health errors may arm the cooldown."""

    def test_typed_status_attribute(self):
        self.assertFalse(_is_health_error(_StatusError(400)))
        self.assertFalse(_is_health_error(_StatusError(403)))
        self.assertTrue(_is_health_error(_StatusError(429)))
        self.assertTrue(_is_health_error(_StatusError(408)))
        self.assertTrue(_is_health_error(_StatusError(500)))
        self.assertTrue(_is_health_error(_StatusError(503)))

    def test_response_status_attribute(self):
        """httpx.HTTPStatusError shape: status lives on ``.response``."""
        exc = Exception("boom")
        exc.response = type("Resp", (), {"status_code": 404})()
        self.assertFalse(_is_health_error(exc))
        exc.response.status_code = 502
        self.assertTrue(_is_health_error(exc))

    def test_message_parse(self):
        self.assertFalse(_is_health_error(Exception("Ollama generate failed (HTTP 400): bad model")))
        self.assertTrue(_is_health_error(Exception("Ollama generate failed (HTTP 503): overloaded")))

    def test_no_status_defaults_to_transient(self):
        """A bare timeout/connection error carries no status but IS
        health-relevant — the conservative default is to cool (#1628)."""
        self.assertTrue(_is_health_error(TimeoutError("timed out")))
        self.assertTrue(_is_health_error(ConnectionError("refused")))
        self.assertTrue(_is_health_error(RuntimeError("unknown provider explosion")))


class TestHealthErrorOnlyCooling(unittest.IsolatedAsyncioTestCase):
    """#1628: request-scoped errors fail over once but never cool the provider."""

    async def test_4xx_does_not_cool_llm_provider(self):
        class FourHundred(FakeLLMClient):
            async def generate(self, *a, **k):
                self.generate_calls += 1
                raise _StatusError(400)

        primary = FourHundred("gemini")
        secondary = FakeLLMClient("ollama")
        client = FallbackLLMClient(primary=primary, fallbacks=[secondary])

        self.assertEqual(await client.generate("one"), "ollama:response")
        self.assertEqual(await client.generate("two"), "ollama:response")
        # No cooldown armed — the primary is retried on every request.
        self.assertEqual(primary.generate_calls, 2)
        self.assertEqual(client._down_until, {})

    async def test_5xx_cools_llm_provider(self):
        class FiveHundred(FakeLLMClient):
            async def generate(self, *a, **k):
                self.generate_calls += 1
                raise _StatusError(503)

        primary = FiveHundred("gemini")
        secondary = FakeLLMClient("ollama")
        client = FallbackLLMClient(primary=primary, fallbacks=[secondary])

        await client.generate("one")
        await client.generate("two")
        self.assertEqual(primary.generate_calls, 1)
        self.assertIn(0, client._down_until)

    async def test_status_in_message_classifies(self):
        """Stringified statuses (Ollama-style) classify the same as typed."""
        primary = _StatusInMessageClient("gemini", status=400)
        secondary = FakeLLMClient("ollama")
        client = FallbackLLMClient(primary=primary, fallbacks=[secondary])

        await client.generate("one")
        await client.generate("two")
        self.assertEqual(primary.generate_calls, 2)
        self.assertEqual(client._down_until, {})

    async def test_4xx_does_not_cool_embedding_primary(self):
        class FourHundred(FakeEmbeddingClient):
            async def embed(self, text):
                self.embed_calls += 1
                raise _StatusError(400)

        primary = FourHundred("gemini")
        secondary = FakeEmbeddingClient("ollama")
        client = FallbackEmbeddingClient(primary=primary, secondary=secondary)

        await client.embed("one")
        await client.embed("two")
        self.assertEqual(primary.embed_calls, 2)
        self.assertEqual(client._primary_down_until, 0.0)


class TestSingleFlightProbe(unittest.IsolatedAsyncioTestCase):
    """#1628: an expired cooldown yields ONE half-open probe — concurrent
    requests skip the recovering provider until the probe resolves."""

    async def test_llm_concurrent_requests_share_one_probe(self):
        probe_gate = asyncio.Event()

        class SlowPrimary(FakeLLMClient):
            async def generate(self, *a, **k):
                self.generate_calls += 1
                await probe_gate.wait()
                return "gemini:response"

        primary = SlowPrimary("gemini")
        secondary = FakeLLMClient("ollama")
        client = FallbackLLMClient(primary=primary, fallbacks=[secondary])
        client._down_until[0] = 0.0  # cooldown just expired → next call probes

        probe = asyncio.create_task(client.generate("probe"))
        # Let the probe start and take the lease before a second request.
        while primary.generate_calls == 0:
            await asyncio.sleep(0)
        second = asyncio.create_task(client.generate("queued"))
        self.assertEqual(await second, "ollama:response")
        probe_gate.set()
        self.assertEqual(await probe, "gemini:response")

        # Exactly one request paid the probe; the other went straight to the
        # fallback. Success then cleared the cooldown and the lease.
        self.assertEqual(primary.generate_calls, 1)
        self.assertEqual(secondary.generate_calls, 1)
        self.assertEqual(client._down_until, {})
        self.assertEqual(client._probe_leases, {})

    async def test_llm_lease_released_on_probe_failure(self):
        """A failed probe re-arms the cooldown AND frees the lease, so the
        next post-cooldown request can probe again."""
        primary = FakeLLMClient("gemini", fail=True)
        secondary = FakeLLMClient("ollama")
        client = FallbackLLMClient(primary=primary, fallbacks=[secondary])
        client._down_until[0] = 0.0

        self.assertEqual(await client.generate("one"), "ollama:response")
        self.assertEqual(client._probe_leases, {})
        self.assertIn(0, client._down_until)

    async def test_embedding_concurrent_embeds_share_one_probe(self):
        probe_gate = asyncio.Event()

        class SlowPrimary(FakeEmbeddingClient):
            async def embed(self, text):
                self.embed_calls += 1
                await probe_gate.wait()
                return [0.9, 0.9]

        primary = SlowPrimary("gemini")
        secondary = FakeEmbeddingClient("ollama")
        client = FallbackEmbeddingClient(primary=primary, secondary=secondary)
        # Expired cooldown → the next embed is the half-open probe.
        client._primary_down_until = time.monotonic() - 1

        probe = asyncio.create_task(client.embed("probe"))
        while primary.embed_calls == 0:
            await asyncio.sleep(0)
        second = asyncio.create_task(client.embed("queued"))
        self.assertEqual(await second, [0.4, 0.5, 0.6])
        probe_gate.set()
        self.assertEqual(await probe, [0.9, 0.9])

        self.assertEqual(primary.embed_calls, 1)
        self.assertEqual(secondary.embed_calls, 1)
        self.assertFalse(client._primary_probing)


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
