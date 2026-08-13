import logging

from config import settings

from .anthropic import AnthropicClient
from .base import BaseLLMClient, EmbeddingClient
from .cohere import CohereClient
from .fallback import FallbackEmbeddingClient, FallbackLLMClient
from .gemini import GeminiClient
from .ollama import OllamaClient
from .openai import OpenAIClient
from .openrouter import OpenRouterClient

logger = logging.getLogger(__name__)

# Default Ollama models used as fallback when the primary provider fails.
_OLLAMA_LLM_FALLBACK_MODEL = "llama3"
_OLLAMA_EMB_FALLBACK_MODEL = "nomic-embed-text"


class ClientFactory:
    """Factory for creating LLM and embedding clients based on model configuration.

    When the primary provider is not Ollama but Ollama is available, the
    factory wraps the primary client in a FallbackLLMClient / FallbackEmbeddingClient
    so that requests transparently fall back to Ollama if the primary fails
    (e.g. invalid API key, quota exhausted, network unreachable). See #568.
    """

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
    def _create_llm_client(
        cls, provider: str, model: str, config: dict
    ) -> BaseLLMClient:
        """Instantiate a raw LLM client for the given provider."""
        if provider == "gemini":
            return GeminiClient(api_key=config["api_key"], model=model)
        elif provider == "openai":
            return OpenAIClient(api_key=config["api_key"], model=model)
        elif provider == "anthropic":
            return AnthropicClient(api_key=config["api_key"], model=model)
        elif provider == "ollama":
            return OllamaClient(base_url=config["base_url"], model=model)
        elif provider == "openrouter":
            return OpenRouterClient(api_key=config["api_key"], model=model)
        elif provider == "cohere":
            return CohereClient(api_key=config["api_key"], model=model)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    @classmethod
    def _create_embedding_client(
        cls, provider: str, model: str, config: dict
    ) -> EmbeddingClient:
        """Instantiate a raw embedding client for the given provider."""
        if provider == "gemini":
            return GeminiClient(api_key=config["api_key"], model=model)
        elif provider == "openai":
            return OpenAIClient(
                api_key=config["api_key"], model=model, is_embedding=True
            )
        elif provider == "cohere":
            return CohereClient(
                api_key=config["api_key"], model=model, is_embedding=True
            )
        elif provider == "ollama":
            return OllamaClient(
                base_url=config["base_url"], model=model, is_embedding=True
            )
        elif provider in ("anthropic", "openrouter"):
            logger.warning(
                f"Provider {provider} doesn't have dedicated embedding, using Ollama fallback"
            )
            if "ollama" in settings.available_providers:
                return OllamaClient(
                    base_url=settings.provider_config["ollama"]["base_url"],
                    model=_OLLAMA_EMB_FALLBACK_MODEL,
                )
            raise ValueError("No embedding provider available")
        else:
            raise ValueError(f"Unknown provider: {provider}")

    @classmethod
    def get_llm_client(cls) -> BaseLLMClient:
        """Get the configured LLM client based on settings.llm_model.

        If the primary provider is not Ollama but Ollama is available,
        wraps the client in a FallbackLLMClient for automatic failover (#568).
        """
        if cls._llm_client is not None:
            return cls._llm_client

        provider, model = cls.parse_model_string(settings.llm_model)
        provider = provider.lower()

        available = settings.available_providers
        logger.info(
            f"Creating LLM client: provider={provider}, model={model}, available={available}"
        )

        if provider not in available:
            raise ValueError(
                f"Provider '{provider}' not configured. Available: {available}"
            )

        config = settings.provider_config[provider]
        primary = cls._create_llm_client(provider, model, config)

        # Wrap with Ollama fallback if primary is not Ollama and Ollama is available
        if provider != "ollama" and "ollama" in available:
            ollama_config = settings.provider_config["ollama"]
            secondary = OllamaClient(
                base_url=ollama_config["base_url"], model=_OLLAMA_LLM_FALLBACK_MODEL
            )
            cls._llm_client = FallbackLLMClient(primary=primary, secondary=secondary)
            logger.info(
                f"LLM client wrapped with Ollama fallback (primary={provider}, secondary=ollama)"
            )
        else:
            cls._llm_client = primary

        return cls._llm_client

    @classmethod
    def get_embedding_client(cls) -> EmbeddingClient:
        """Get the configured embedding client based on settings.embedding_model.

        If the primary provider is not Ollama but Ollama is available,
        wraps the client in a FallbackEmbeddingClient for automatic failover (#568).
        """
        if cls._embedding_client is not None:
            return cls._embedding_client

        provider, model = cls.parse_model_string(settings.embedding_model)
        provider = provider.lower()

        available = settings.available_providers

        if provider not in available:
            raise ValueError(
                f"Provider '{provider}' not configured. Available: {available}"
            )

        config = settings.provider_config[provider]
        primary = cls._create_embedding_client(provider, model, config)

        # Wrap with Ollama fallback if primary is not Ollama and Ollama is available.
        # Skip if primary is already Ollama (e.g. anthropic/openrouter embedding fallback).
        if (
            provider != "ollama"
            and "ollama" in available
            and not isinstance(primary, OllamaClient)
        ):
            ollama_config = settings.provider_config["ollama"]
            secondary = OllamaClient(
                base_url=ollama_config["base_url"],
                model=_OLLAMA_EMB_FALLBACK_MODEL,
                is_embedding=True,
            )
            cls._embedding_client = FallbackEmbeddingClient(
                primary=primary, secondary=secondary
            )
            logger.info(
                f"Embedding client wrapped with Ollama fallback (primary={provider}, secondary=ollama)"
            )
        else:
            cls._embedding_client = primary

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
