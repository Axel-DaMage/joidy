"""Unit tests for clients/base.py: parse_classification + classify()/health_check() defaults."""

import unittest

from clients.base import BaseLLMClient, EmbeddingClient, parse_classification


class _FakeLLM(BaseLLMClient):
    def __init__(self, response: str = "[]", fail: bool = False):
        self._response = response
        self._fail = fail
        self.last_prompt: str | None = None
        self.last_kwargs: dict[str, float] | None = None

    @property
    def provider_name(self) -> str:
        return "fake"

    async def embed_text(self, text: str) -> list[float]:
        return [0.0]

    async def generate(self, prompt: str, temperature: float = 0.2, max_tokens: int = 256, system_prompt=None) -> str:
        if self._fail:
            raise RuntimeError("boom")
        self.last_prompt = prompt
        self.last_kwargs = {"temperature": temperature, "max_tokens": max_tokens}
        return self._response


class _FakeEmb(EmbeddingClient):
    def __init__(self, fail: bool = False):
        self._fail = fail

    @property
    def provider_name(self) -> str:
        return "fake-emb"

    async def embed(self, text: str) -> list[float]:
        if self._fail:
            raise RuntimeError("boom")
        return [0.1, 0.2]


class TestParseClassification(unittest.TestCase):
    def test_parses_json_array(self):
        text = '[{"tag": "Python", "confidence": 0.9, "is_new": true}]'
        result = parse_classification(text, [])
        self.assertEqual(result, [{"tag": "python", "confidence": 0.9, "is_new": True}])

    def test_extracts_array_embedded_in_text(self):
        text = 'Here are tags: [{"tag": "ml", "confidence": 0.5}] done.'
        result = parse_classification(text, ["ml"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["tag"], "ml")

    def test_is_new_defaults_to_membership_check(self):
        text = '[{"tag": "existing", "confidence": 0.8}, {"tag": "brand-new", "confidence": 0.6}]'
        result = parse_classification(text, ["existing"])
        self.assertFalse(result[0]["is_new"])
        self.assertTrue(result[1]["is_new"])

    def test_missing_confidence_key_is_skipped(self):
        # The parser requires both "tag" and "confidence" keys.
        self.assertEqual(parse_classification('[{"tag": "x"}]', []), [])

    def test_no_json_returns_empty(self):
        self.assertEqual(parse_classification("no json here", []), [])

    def test_malformed_json_returns_empty(self):
        self.assertEqual(parse_classification("[{not valid}]", []), [])

    def test_entries_missing_fields_are_skipped(self):
        text = '[{"tag": "ok", "confidence": 0.7}, {"no_tag": true}, "stray"]'
        result = parse_classification(text, [])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["tag"], "ok")


class TestBaseLLMClientClassify(unittest.IsolatedAsyncioTestCase):
    async def test_classify_formats_prompt_and_parses(self):
        client = _FakeLLM(response='[{"tag": "ai", "confidence": 0.9}]')
        result = await client.classify("note content", ["old"], "Tags: {existing_tags} | {content}")
        self.assertEqual(result[0]["tag"], "ai")
        self.assertIn("old", client.last_prompt)
        self.assertIn("note content", client.last_prompt)

    async def test_classify_uses_placeholder_when_no_tags(self):
        client = _FakeLLM(response="[]")
        await client.classify("c", [], "existing={existing_tags} content={content}")
        self.assertIn("ninguno aún", client.last_prompt)

    async def test_classify_truncates_content_to_2000_chars(self):
        client = _FakeLLM(response="[]")
        await client.classify("x" * 5000, [], "{content}")
        self.assertEqual(len(client.last_prompt), 2000)


class TestHealthCheckDefaults(unittest.IsolatedAsyncioTestCase):
    async def test_llm_health_check_true_on_success(self):
        self.assertTrue(await _FakeLLM().health_check())

    async def test_llm_health_check_false_on_failure(self):
        self.assertFalse(await _FakeLLM(fail=True).health_check())

    async def test_embedding_health_check_true_on_success(self):
        self.assertTrue(await _FakeEmb().health_check())

    async def test_embedding_health_check_false_on_failure(self):
        self.assertFalse(await _FakeEmb(fail=True).health_check())


if __name__ == "__main__":
    unittest.main()
