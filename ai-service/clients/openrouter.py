import logging

import aiohttp

from .base import BaseLLMClient

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_OPENROUTER_TIMEOUT = aiohttp.ClientTimeout(total=60)


class OpenRouterClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str):
        self._api_key = api_key
        self._model = model
        self._session: aiohttp.ClientSession | None = None

    @property
    def provider_name(self) -> str:
        return "openrouter"

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=_OPENROUTER_TIMEOUT)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError("Use dedicated embedding provider")

    async def embed(self, text: str) -> list[float]:
        raise NotImplementedError("Use dedicated embedding provider")

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 256,
        system_prompt: str | None = None,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        session = await self._get_session()
        async with session.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json={
                "model": self._model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        ) as resp:
            if resp.status != 200:
                raise Exception(f"OpenRouter failed: {await resp.text()}")
            data = await resp.json()
            return data["choices"][0]["message"]["content"]
