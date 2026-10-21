"""Mocked unit tests for provider clients.

Each provider gets at least: success path, retry-on-rate-limit path, and
error-mapping path. No real network or API keys are used — SDK entry points
and HTTP sessions are replaced with mocks/fakes.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from config import settings

# Fast retry settings so retry-path tests don't sleep for real.
_FAST_RETRY = {"ai_retry_max_attempts": 3, "ai_retry_base_delay_seconds": 0.1}


def _fast_retry():
    """Context manager patching retry knobs to near-instant values."""
    return patch.multiple(settings, **_FAST_RETRY)


class _FakeResponse:
    """Minimal aiohttp response stand-in usable with `async with`."""

    def __init__(self, status: int = 200, payload=None, text: str = ""):
        self.status = status
        self._payload = payload if payload is not None else {}
        self._text = text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def json(self):
        return self._payload

    async def text(self):
        return self._text


class _FakeSession:
    """Minimal aiohttp.ClientSession stand-in recording requests."""

    closed = False

    def __init__(self, post_resp=None, get_resp=None, post_error=None):
        self._post_resp = post_resp
        self._get_resp = get_resp
        self._post_error = post_error
        self.posts: list[tuple] = []
        self.gets: list[tuple] = []

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        if self._post_error is not None:
            raise self._post_error
        return self._post_resp

    def get(self, url, **kwargs):
        self.gets.append((url, kwargs))
        return self._get_resp

    async def close(self):
        pass


# ── Gemini ─────────────────────────────────────────────────────────────


class TestGeminiClient(unittest.IsolatedAsyncioTestCase):
    async def test_embed_success(self):
        from clients.gemini import GeminiClient

        with patch("clients.gemini.genai") as mock_genai:
            mock_genai.embed_content.return_value = {"embedding": [0.1, 0.2, 0.3]}
            client = GeminiClient(api_key="fake", model="models/text-embedding-004")
            result = await client.embed("hello")

        self.assertEqual(result, [0.1, 0.2, 0.3])
        mock_genai.embed_content.assert_called_once()
        self.assertEqual(mock_genai.embed_content.call_args.kwargs["content"], "hello")

    async def test_generate_success(self):
        from clients.gemini import GeminiClient

        with patch("clients.gemini.genai") as mock_genai:
            model = mock_genai.GenerativeModel.return_value
            model.generate_content.return_value = MagicMock(text="generated text")
            client = GeminiClient(api_key="fake", model="gemini-2.0-flash")
            result = await client.generate("prompt", temperature=0.5, max_tokens=64)

        self.assertEqual(result, "generated text")
        model.generate_content.assert_called_once()
        self.assertEqual(model.generate_content.call_args[0][0], "prompt")

    async def test_retry_on_rate_limit_then_success(self):
        from clients.gemini import _call_with_retry

        calls = []

        def flaky():
            calls.append(1)
            if len(calls) == 1:
                raise Exception("429 Resource exhausted")
            return "recovered"

        with _fast_retry():
            result = await _call_with_retry(flaky)
        self.assertEqual(result, "recovered")
        self.assertEqual(len(calls), 2)

    async def test_non_retryable_error_raises_immediately(self):
        from clients.gemini import _call_with_retry

        calls = []

        def bad_key():
            calls.append(1)
            raise RuntimeError("API key not valid")

        with _fast_retry(), self.assertRaises(RuntimeError):
            await _call_with_retry(bad_key)
        self.assertEqual(len(calls), 1)

    async def test_retry_exhaustion_raises_last_error(self):
        from clients.gemini import _call_with_retry

        def always_limited():
            raise Exception("429 rate limit")

        with _fast_retry(), self.assertRaises(Exception) as ctx:
            await _call_with_retry(always_limited)
        self.assertIn("429", str(ctx.exception))

    async def test_timeout_maps_to_timeout_error(self):
        import asyncio

        from clients.gemini import _call_with_retry

        def slow():
            import time

            time.sleep(0.5)
            return "late"

        with self.assertRaises(TimeoutError):
            await _call_with_retry(slow, timeout=0.05)
        # Suppress un-retrieved executor future noise.
        await asyncio.sleep(0)

    def test_is_retryable_error_matching(self):
        from clients.gemini import _is_retryable_error

        self.assertTrue(_is_retryable_error(Exception("HTTP 429")))
        self.assertTrue(_is_retryable_error(Exception("Resource exhausted")))
        self.assertFalse(_is_retryable_error(Exception("invalid api key")))

    def test_embedding_bytes_roundtrip(self):
        from clients.gemini import bytes_to_embedding, embedding_to_bytes

        # float32-exact values so the roundtrip is bit-precise
        vec = [0.5, -0.25, 3.5]
        self.assertEqual(bytes_to_embedding(embedding_to_bytes(vec)), vec)


# ── OpenAI ─────────────────────────────────────────────────────────────


class TestOpenAIClient(unittest.IsolatedAsyncioTestCase):
    def _make_client(self, is_embedding: bool = False):
        from clients.openai import OpenAIClient

        with patch("clients.openai.AsyncOpenAI") as mock_cls:
            client = OpenAIClient(api_key="fake", model="gpt-4o-mini", is_embedding=is_embedding)
        return client, mock_cls.return_value

    async def test_embed_success(self):
        client, inst = self._make_client(is_embedding=True)
        resp = MagicMock()
        resp.data = [MagicMock(embedding=[0.4, 0.5])]
        inst.embeddings.create = AsyncMock(return_value=resp)

        result = await client.embed("text")
        self.assertEqual(result, [0.4, 0.5])
        inst.embeddings.create.assert_awaited_once_with(model="gpt-4o-mini", input="text")

    async def test_generate_success_with_system_prompt(self):
        client, inst = self._make_client()
        resp = MagicMock()
        resp.choices = [MagicMock(message=MagicMock(content="openai says"))]
        inst.chat.completions.create = AsyncMock(return_value=resp)

        result = await client.generate("hi", system_prompt="be brief")
        self.assertEqual(result, "openai says")

        kwargs = inst.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["messages"][0], {"role": "system", "content": "be brief"})
        self.assertEqual(kwargs["messages"][1], {"role": "user", "content": "hi"})

    async def test_retry_on_rate_limit(self):
        client, inst = self._make_client()
        resp = MagicMock()
        resp.choices = [MagicMock(message=MagicMock(content="ok"))]
        inst.chat.completions.create = AsyncMock(side_effect=[Exception("429 rate_limit_exceeded"), resp])

        with _fast_retry():
            result = await client.generate("hi")
        self.assertEqual(result, "ok")
        self.assertEqual(inst.chat.completions.create.await_count, 2)

    async def test_non_retryable_error_propagates(self):
        client, inst = self._make_client()
        inst.chat.completions.create = AsyncMock(side_effect=Exception("invalid api key"))

        with _fast_retry(), self.assertRaises(Exception) as ctx:
            await client.generate("hi")
        self.assertIn("invalid api key", str(ctx.exception))
        self.assertEqual(inst.chat.completions.create.await_count, 1)

    def test_is_retryable_error_matching(self):
        from clients.openai import _is_retryable_error

        self.assertTrue(_is_retryable_error(Exception("429")))
        self.assertTrue(_is_retryable_error(Exception("rate_limit")))
        self.assertFalse(_is_retryable_error(Exception("bad request")))


# ── Anthropic ──────────────────────────────────────────────────────────


class TestAnthropicClient(unittest.IsolatedAsyncioTestCase):
    def _make_client(self):
        from clients.anthropic import AnthropicClient

        with patch("clients.anthropic.anthropic.AsyncAnthropic") as mock_cls:
            client = AnthropicClient(api_key="fake", model="claude-3-haiku")
        return client, mock_cls.return_value

    async def test_generate_success(self):
        client, inst = self._make_client()
        resp = MagicMock()
        resp.content = [MagicMock(text="claude says")]
        inst.messages.create = AsyncMock(return_value=resp)

        result = await client.generate("hi", system_prompt="sys")
        self.assertEqual(result, "claude says")
        kwargs = inst.messages.create.call_args.kwargs
        self.assertEqual(kwargs["system"], "sys")
        self.assertEqual(kwargs["messages"], [{"role": "user", "content": "hi"}])

    async def test_retry_on_overloaded(self):
        client, inst = self._make_client()
        resp = MagicMock()
        resp.content = [MagicMock(text="ok")]
        inst.messages.create = AsyncMock(side_effect=[Exception("overloaded"), resp])

        with _fast_retry():
            result = await client.generate("hi")
        self.assertEqual(result, "ok")
        self.assertEqual(inst.messages.create.await_count, 2)

    async def test_non_retryable_error_propagates(self):
        client, inst = self._make_client()
        inst.messages.create = AsyncMock(side_effect=RuntimeError("auth failed"))

        with _fast_retry(), self.assertRaises(RuntimeError):
            await client.generate("hi")
        self.assertEqual(inst.messages.create.await_count, 1)

    async def test_embed_raises_not_implemented(self):
        client, _ = self._make_client()
        with self.assertRaises(NotImplementedError):
            await client.embed("text")
        with self.assertRaises(NotImplementedError):
            await client.embed_text("text")

    def test_is_retryable_error_matching(self):
        from clients.anthropic import _is_retryable_error

        self.assertTrue(_is_retryable_error(Exception("overloaded")))
        self.assertFalse(_is_retryable_error(Exception("not found")))


# ── Cohere ─────────────────────────────────────────────────────────────


class TestCohereClient(unittest.IsolatedAsyncioTestCase):
    def _make_client(self, is_embedding: bool = False):
        from clients.cohere import CohereClient

        with patch("clients.cohere.cohere.AsyncClient") as mock_cls:
            client = CohereClient(api_key="fake", model="embed-v4", is_embedding=is_embedding)
        return client, mock_cls.return_value

    async def test_embed_success(self):
        client, inst = self._make_client(is_embedding=True)
        inst.embed = AsyncMock(return_value=MagicMock(embeddings=[[0.7, 0.8]]))

        result = await client.embed("text")
        self.assertEqual(result, [0.7, 0.8])
        self.assertEqual(inst.embed.call_args.kwargs["texts"], ["text"])

    async def test_generate_success_with_preamble(self):
        client, inst = self._make_client()
        inst.chat = AsyncMock(return_value=MagicMock(text="cohere!"))

        result = await client.generate("hi", system_prompt="pre")
        self.assertEqual(result, "cohere!")
        kwargs = inst.chat.call_args.kwargs
        self.assertEqual(kwargs["message"], "hi")
        self.assertEqual(kwargs["preamble"], "pre")

    async def test_retry_on_rate_limit(self):
        client, inst = self._make_client()
        inst.chat = AsyncMock(side_effect=[Exception("429 too many"), MagicMock(text="ok")])

        with _fast_retry():
            result = await client.generate("hi")
        self.assertEqual(result, "ok")
        self.assertEqual(inst.chat.await_count, 2)

    async def test_non_retryable_error_propagates(self):
        client, inst = self._make_client()
        inst.chat = AsyncMock(side_effect=RuntimeError("unauthorized"))

        with _fast_retry(), self.assertRaises(RuntimeError):
            await client.generate("hi")
        self.assertEqual(inst.chat.await_count, 1)


# ── Ollama (aiohttp) ──────────────────────────────────────────────────


class TestOllamaClient(unittest.IsolatedAsyncioTestCase):
    def _make_client(self, session, is_embedding: bool = False):
        from clients.ollama import OllamaClient

        client = OllamaClient(base_url="http://ollama:11434/", model="llama3", is_embedding=is_embedding)
        client._session = session
        return client

    async def test_embed_success(self):
        session = _FakeSession(post_resp=_FakeResponse(200, {"embedding": [0.9, 0.1]}))
        client = self._make_client(session, is_embedding=True)

        result = await client.embed("text")
        self.assertEqual(result, [0.9, 0.1])
        url, kwargs = session.posts[0]
        self.assertEqual(url, "http://ollama:11434/api/embeddings")
        self.assertEqual(kwargs["json"], {"model": "llama3", "prompt": "text"})

    async def test_embed_error_status_raises(self):
        session = _FakeSession(post_resp=_FakeResponse(500, text="model missing"))
        client = self._make_client(session, is_embedding=True)

        with self.assertRaises(Exception) as ctx:
            await client.embed("text")
        self.assertIn("Ollama embedding failed", str(ctx.exception))

    async def test_generate_success_and_payload_shape(self):
        session = _FakeSession(post_resp=_FakeResponse(200, {"response": "ollama says"}))
        client = self._make_client(session)

        result = await client.generate("hi", temperature=0.3, max_tokens=64, system_prompt="sys")
        self.assertEqual(result, "ollama says")
        url, kwargs = session.posts[0]
        self.assertEqual(url, "http://ollama:11434/api/generate")
        self.assertEqual(kwargs["json"]["prompt"], "sys\n\nhi")
        self.assertEqual(kwargs["json"]["options"], {"num_predict": 64})
        self.assertEqual(kwargs["json"]["temperature"], 0.3)

    async def test_generate_error_status_raises(self):
        session = _FakeSession(post_resp=_FakeResponse(404, text="no model"))
        client = self._make_client(session)

        with self.assertRaises(Exception) as ctx:
            await client.generate("hi")
        self.assertIn("Ollama generate failed", str(ctx.exception))

    async def test_health_check_true_on_200(self):
        session = _FakeSession(get_resp=_FakeResponse(200, {}))
        client = self._make_client(session)
        self.assertTrue(await client.health_check())
        self.assertEqual(session.gets[0][0], "http://ollama:11434/api/tags")

    async def test_health_check_false_on_exception(self):
        class BoomSession(_FakeSession):
            def get(self, url, **kwargs):
                raise ConnectionError("refused")

        client = self._make_client(BoomSession())
        self.assertFalse(await client.health_check())


# ── OpenRouter (aiohttp) ──────────────────────────────────────────────


class TestOpenRouterClient(unittest.IsolatedAsyncioTestCase):
    def _make_client(self, session):
        from clients.openrouter import OpenRouterClient

        client = OpenRouterClient(api_key="sk-or-fake", model="openai/gpt-4o")
        client._session = session
        return client

    async def test_generate_success_payload_and_auth(self):
        payload = {"choices": [{"message": {"content": "router answer"}}]}
        session = _FakeSession(post_resp=_FakeResponse(200, payload))
        client = self._make_client(session)

        result = await client.generate("hi", system_prompt="sys", max_tokens=32)
        self.assertEqual(result, "router answer")

        url, kwargs = session.posts[0]
        self.assertTrue(url.endswith("/chat/completions"))
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer sk-or-fake")
        self.assertEqual(kwargs["json"]["model"], "openai/gpt-4o")
        self.assertEqual(kwargs["json"]["messages"][0], {"role": "system", "content": "sys"})
        self.assertEqual(kwargs["json"]["messages"][1], {"role": "user", "content": "hi"})
        self.assertEqual(kwargs["json"]["max_tokens"], 32)

    async def test_generate_error_status_raises(self):
        session = _FakeSession(post_resp=_FakeResponse(429, text="limited"))
        client = self._make_client(session)

        with self.assertRaises(Exception) as ctx:
            await client.generate("hi")
        self.assertIn("OpenRouter failed", str(ctx.exception))

    async def test_embed_raises_not_implemented(self):
        client = self._make_client(_FakeSession())
        with self.assertRaises(NotImplementedError):
            await client.embed("text")
        with self.assertRaises(NotImplementedError):
            await client.embed_text("text")


if __name__ == "__main__":
    unittest.main()
