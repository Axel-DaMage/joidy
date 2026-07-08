import logging

from config import settings

from .anthropic import AnthropicClient
from .base import BaseLLMClient, EmbeddingClient
from .cohere import CohereClient
from .gemini import GeminiClient
from .ollama import OllamaClient
from .openai import OpenAIClient
from .openrouter import OpenRouterClient

logger = logging.getLogger(__name__)


class ClientFactory:
    """Factory for creating LLM and embedding clients based on model configuration."""

    _llm_client: BaseLLMClient | None = None
    _embedding_client: EmbeddingClient | None = None

    @classmethod
    def parse_model_string(cls, model: str) -> tuple[str, str]:
        """Parse 'provider:model' format. Returns (provider, model_name)."""
        if ":" in model:
            parts = model.split(":", 1)
            return parts[0], parts[1]
        return "gemini", model

    @classmethod
    def get_llm_client(cls) -> BaseLLMClient:
        """Get the configured LLM client based on settings.llm_model."""
        if cls._llm_client is not None:
            return cls._llm_client

        provider, model = cls.parse_model_string(settings.llm_model)
        provider = provider.lower()

        available = settings.available_providers
        logger.info(f"Creating LLM client: provider={provider}, model={model}, available={available}")

        if provider not in available:
            raise ValueError(f"Provider '{provider}' not configured. Available: {available}")

        config = settings.provider_config[provider]

        if provider == "gemini":
            cls._llm_client = GeminiClient(api_key=config["api_key"], model=model)
        elif provider == "openai":
            cls._llm_client = OpenAIClient(api_key=config["api_key"], model=model)
        elif provider == "anthropic":
            cls._llm_client = AnthropicClient(api_key=config["api_key"], model=model)
        elif provider == "ollama":
            cls._llm_client = OllamaClient(base_url=config["base_url"], model=model)
        elif provider == "openrouter":
            cls._llm_client = OpenRouterClient(api_key=config["api_key"], model=model)
        elif provider == "cohere":
            cls._llm_client = CohereClient(api_key=config["api_key"], model=model)
        else:
            raise ValueError(f"Unknown provider: {provider}")

        return cls._llm_client

    @classmethod
    def get_embedding_client(cls) -> EmbeddingClient:
        """Get the configured embedding client based on settings.embedding_model."""
        if cls._embedding_client is not None:
            return cls._embedding_client

        provider, model = cls.parse_model_string(settings.embedding_model)
        provider = provider.lower()

        available = settings.available_providers

        if provider not in available:
            raise ValueError(f"Provider '{provider}' not configured. Available: {available}")

        config = settings.provider_config[provider]

        if provider == "gemini":
            cls._embedding_client = GeminiClient(api_key=config["api_key"], model=model)
        elif provider == "openai":
            cls._embedding_client = OpenAIClient(api_key=config["api_key"], model=model, is_embedding=True)
        elif provider == "cohere":
            cls._embedding_client = CohereClient(api_key=config["api_key"], model=model, is_embedding=True)
        elif provider == "ollama":
            cls._embedding_client = OllamaClient(base_url=config["base_url"], model=model, is_embedding=True)
        elif provider in ("anthropic", "openrouter"):
            logger.warning(f"Provider {provider} doesn't have dedicated embedding, using Ollama fallback")
            if "ollama" in available:
                cls._embedding_client = OllamaClient(base_url=settings.provider_config["ollama"]["base_url"], model="nomic-embed-text")
            else:
                raise ValueError("No embedding provider available")
        else:
            raise ValueError(f"Unknown provider: {provider}")

        return cls._embedding_client

    @classmethod
    def reset(cls):
        """Reset cached clients (useful for testing)."""
        cls._llm_client = None
        cls._embedding_client = None


def get_llm_client() -> BaseLLMClient:
    return ClientFactory.get_llm_client()


def get_embedding_client() -> EmbeddingClient:
    return ClientFactory.get_embedding_client()
