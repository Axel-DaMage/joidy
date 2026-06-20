import asyncio
import logging
from typing import Optional

import anthropic

from .base import BaseLLMClient
from config import settings

logger = logging.getLogger(__name__)


class AnthropicClient(BaseLLMClient):
    def __init__(self, api_key: str, model: str):
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError("Anthropic doesn't provide embeddings API")

    async def embed(self, text: str) -> list[float]:
        raise NotImplementedError("Anthropic doesn't provide embeddings API")

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 256,
        system_prompt: Optional[str] = None,
    ) -> str:
        response = await _call_with_retry(
            self._client.messages.create,
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text


def _is_retryable_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "rate_limit" in msg or "overloaded" in msg


async def _call_with_retry(func, *args, **kwargs):
    attempts = max(1, settings.ai_retry_max_attempts)
    base = max(0.1, settings.ai_retry_base_delay_seconds)
    cap = max(base, settings.ai_retry_max_delay_seconds)

    for attempt in range(1, attempts + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            if not _is_retryable_error(exc) or attempt >= attempts:
                raise
            delay = min(cap, base * (2 ** (attempt - 1)))
            logger.warning(f"Anthropic call failed. attempt={attempt}/{attempts} delay={delay:.2f}s error={exc}")
            await asyncio.sleep(delay)