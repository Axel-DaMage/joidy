import logging
from typing import cast

import aiohttp
from config import settings, validate_base_url

from .base import BaseLLMClient, EmbeddingClient
from .retry import call_with_retry

logger = logging.getLogger(__name__)


class OllamaClient(BaseLLMClient, EmbeddingClient):
    def __init__(self, base_url: str, model: str, is_embedding: bool = False):
        # Fail fast on insecure/malformed URLs: http:// is only allowed for
        # loopback targets since Ollama is expected to be local (#1330).
        self._base_url = validate_base_url(
            base_url, name="OLLAMA_BASE_URL", allow_insecure=settings.allow_insecure_base_urls
        )
        self._model = model
        self._is_embedding = is_embedding
        self._session: aiohttp.ClientSession | None = None

    @property
    def provider_name(self) -> str:
        return "ollama"

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            total = settings.embed_timeout if self._is_embedding else settings.llm_timeout
            timeout = aiohttp.ClientTimeout(total=total, connect=settings.connect_timeout)
            # trust_env=False: ignore ambient HTTP(S)_PROXY env vars (#1330).
            self._session = aiohttp.ClientSession(timeout=timeout, trust_env=False)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def embed_text(self, text: str) -> list[float]:
        return await self.embed(text)

    async def embed(self, text: str) -> list[float]:
        return cast("list[float]", await call_with_retry(self._embed_once, text, provider="Ollama"))

    async def _embed_once(self, text: str) -> list[float]:
        session = await self._get_session()
        async with session.post(
            f"{self._base_url}/api/embeddings",
            json={"model": self._model, "prompt": text},
        ) as resp:
            if resp.status != 200:
                # The status rides in the message so both the retryable predicate
                # (#1540) and the failover wrapper (#1628) can classify it.
                raise Exception(f"Ollama embedding failed (HTTP {resp.status}): {await resp.text()}")
            data = await resp.json()
            return cast("list[float]", data["embedding"])

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 256,
        system_prompt: str | None = None,
    ) -> str:
        payload = {
            "model": self._model,
            "prompt": prompt,
            "temperature": temperature,
            "options": {"num_predict": max_tokens},
        }
        if system_prompt:
            # Send the system prompt in its own field instead of smashing it
            # together with user content — keeps roles separated (#1330).
            payload["system"] = system_prompt
        return cast("str", await call_with_retry(self._generate_once, payload, provider="Ollama"))

    async def _generate_once(self, payload: dict) -> str:
        session = await self._get_session()
        async with session.post(
            f"{self._base_url}/api/generate",
            json=payload,
        ) as resp:
            if resp.status != 200:
                # Same: HTTP status in the message for retry/failover classification.
                raise Exception(f"Ollama generate failed (HTTP {resp.status}): {await resp.text()}")
            data = await resp.json()
            return cast("str", data["response"])

    async def health_check(self) -> bool:
        """Check if Ollama is reachable via GET /api/tags (lightweight, no model load)."""
        try:
            session = await self._get_session()
            async with session.get(f"{self._base_url}/api/tags") as resp:
                return cast("bool", resp.status == 200)
        except Exception:
            return False
