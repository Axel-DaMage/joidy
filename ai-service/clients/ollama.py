import logging

import aiohttp

from .base import BaseLLMClient, EmbeddingClient

logger = logging.getLogger(__name__)


class OllamaClient(BaseLLMClient, EmbeddingClient):
    def __init__(self, base_url: str, model: str, is_embedding: bool = False):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._is_embedding = is_embedding

    @property
    def provider_name(self) -> str:
        return "ollama"

    async def embed_text(self, text: str) -> list[float]:
        return await self.embed(text)

    async def embed(self, text: str) -> list[float]:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self._base_url}/api/embeddings",
                json={"model": self._model, "prompt": text},
            ) as resp:
                if resp.status != 200:
                    raise Exception(f"Ollama embedding failed: {await resp.text()}")
                data = await resp.json()
                return data["embedding"]

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 256,
        system_prompt: str | None = None,
    ) -> str:
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": full_prompt,
                    "temperature": temperature,
                    "options": {"num_predict": max_tokens},
                },
            ) as resp:
                if resp.status != 200:
                    raise Exception(f"Ollama generate failed: {await resp.text()}")
                data = await resp.json()
                return data["response"]
