import asyncio
import logging
from typing import Optional

import aiohttp

from .base import BaseLLMClient
from config import settings

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str):
        self._api_key = api_key
        self._model = model

    @property
    def provider_name(self) -> str:
        return "openrouter"

    async def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError("Use dedicated embedding provider")

    async def embed(self, text: str) -> list[float]:
        raise NotImplementedError("Use dedicated embedding provider")

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 256,
        system_prompt: Optional[str] = None,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async with aiohttp.ClientSession() as session:
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