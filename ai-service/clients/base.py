from abc import ABC, abstractmethod
from typing import Optional


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
        system_prompt: Optional[str] = None,
    ) -> str:
        """Generate text response."""
        pass

    @abstractmethod
    async def classify(
        self,
        content: str,
        existing_tags: list[str],
        classify_prompt: str,
    ) -> list[dict]:
        """
        Classify content and return tag suggestions.
        Returns: [{"tag": str, "confidence": float, "is_new": bool}, ...]
        """
        pass


class EmbeddingClient(ABC):
    """Abstract base class for embedding providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        pass