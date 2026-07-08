import json
import re
from abc import ABC, abstractmethod


class BaseLLMClient(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier."""
        pass

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding vector."""
        pass

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 256,
        system_prompt: str | None = None,
    ) -> str:
        """Generate text response."""
        pass

    async def classify(
        self,
        content: str,
        existing_tags: list[str],
        classify_prompt: str,
    ) -> list[dict]:
        """
        Classify content and return tag suggestions by delegating to generate() and parse_classification().
        """
        prompt = classify_prompt.format(
            content=content[:2000],
            existing_tags=", ".join(existing_tags) if existing_tags else "ninguno aún"
        )
        result = await self.generate(prompt, temperature=0.2, max_tokens=256)
        return parse_classification(result, existing_tags)


def parse_classification(text: str, existing_tags: list[str]) -> list[dict]:
    """Helper to parse JSON array of tag suggestions from LLM text response."""
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


class EmbeddingClient(ABC):
    """Abstract base class for embedding providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        pass
