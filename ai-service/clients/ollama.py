import asyncio
import logging
from typing import Optional

import aiohttp

from .base import BaseLLMClient, EmbeddingClient
from config import settings

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
        system_prompt: Optional[str] = None,
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

    async def classify(
        self,
        content: str,
        existing_tags: list[str],
        classify_prompt: str,
    ) -> list[dict]:
        prompt = classify_prompt.format(
            content=content[:2000],
            existing_tags=", ".join(existing_tags) if existing_tags else "ninguno aún"
        )
        result = await self.generate(prompt, temperature=0.2, max_tokens=256)
        return _parse_classification(result, existing_tags)


def _parse_classification(text: str, existing_tags: list[str]) -> list[dict]:
    import json
    import re

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        suggestions = json.loads(match.group())
        result = []
        for s in suggestions:
            if isinstance(s, dict) and "tag" in s and "confidence" in s:
                result.append({
                    "tag": str(s["tag"]).lower().strip(),
                    "confidence": float(s.get("confidence", 0.5)),
                    "is_new": s.get("is_new", s["tag"] not in existing_tags),
                })
        return result
    except (json.JSONDecodeError, KeyError, ValueError):
        return []