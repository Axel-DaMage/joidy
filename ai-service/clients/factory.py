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

# Default models per provider when falling back (the configured model name
# belongs to the original provider and is not valid for the fallback one).
FALLBACK_LLM_MODELS: dict[str, str] = {
    "ollama": "llama3",
    "openai": "gpt-4o-mini",
    "cohere": "command-r-plus",
    "anthropic": "claude-3-5-sonnet-20241022",
    "openrouter": "openai/gpt-4o-mini",
    "gemini": "gemini-2.0-flash",
}

FALLBACK_EMBEDDING_MODELS: dict[str, str] = {
    "ollama": "nomic-embed-text",
    "openai": "text-embedding-3-small",
    "cohere": "embed-english-v3.0",
    "gemini": "models/text-embedding-004",
}

# Providers that don't offer embeddings — skipped during embedding fallback.
_NO_EMBEDDING_PROVIDERS = frozenset({"anthropic", "openrouter"})

# Preference order when falling back: local/free providers first.
_FALLBACK_ORDER = ("ollama", "openai", "cohere", "gemini", "anthropic", "openrouter")


class ClientFactory:
    """Factory for creating LLM and embedding clients based on model configuration."""

    _llm_client: BaseLLMClient | None = None
    _embedding_client: EmbeddingClient | None = None
    # Track the actual provider used after fallback so /health can report it.
    _llm_provider_used: str | None = None
    _embedding_provider_used: str | None = None
    _llm_model_used: str | None = None
    _embedding_model_used: str | None = None

    @classmethod
    def parse_model_string(cls, model: str) -> tuple[str, str]:
        """Parse 'provider:model' format. Returns (provider, model_name)."""
        if ":" in model:
            parts = model.split(":", 1)
            return parts[0], parts[1]
        return "gemini", model

    @classmethod
    def _create_llm_client(cls, provider: str, model: str) -> BaseLLMClient:
        """Instantiate an LLM client for *provider* with *model*."""
        config = settings.provider_config[provider]
        if provider == "gemini":
            return GeminiClient(api_key=config["api_key"], model=model)
        if provider == "openai":
            return OpenAIClient(api_key=config["api_key"], model=model)
        if provider == "anthropic":
            return AnthropicClient(api_key=config["api_key"], model=model)
        if provider == "ollama":
            return OllamaClient(base_url=config["base_url"], model=model)
        if provider == "openrouter":
            return OpenRouterClient(api_key=config["api_key"], model=model)
        if provider == "cohere":
            return CohereClient(api_key=config["api_key"], model=model)
        raise ValueError(f"Unknown provider: {provider}")

    @classmethod
    def _create_embedding_client(cls, provider: str, model: str) -> EmbeddingClient:
        """Instantiate an embedding client for *provider* with *model*."""
        config = settings.provider_config[provider]
        if provider == "gemini":
            return GeminiClient(api_key=config["api_key"], model=model)
        if provider == "openai":
            return OpenAIClient(api_key=config["api_key"], model=model, is_embedding=True)
        if provider == "cohere":
            return CohereClient(api_key=config["api_key"], model=model, is_embedding=True)
        if provider == "ollama":
            return OllamaClient(base_url=config["base_url"], model=model, is_embedding=True)
        raise ValueError(f"Provider '{provider}' does not support embeddings")

    @classmethod
    def _resolve_fallback(cls, kind: str, configured_provider: str, configured_model: str) -> tuple[str, str]:
        """Find an available fallback provider+model.

        Returns (provider, model). Raises ValueError if none available.
        """
        available = settings.available_providers
        models = FALLBACK_EMBEDDING_MODELS if kind == "embedding" else FALLBACK_LLM_MODELS
        for candidate in _FALLBACK_ORDER:
            if candidate == configured_provider:
                continue
            if candidate not in available:
                continue
            if kind == "embedding" and candidate in _NO_EMBEDDING_PROVIDERS:
                continue
            fallback_model = models.get(candidate)
            if not fallback_model:
                continue
            logger.warning(
                f"Provider '{configured_provider}' not available — falling back to "
                f"{kind} provider '{candidate}' with model '{fallback_model}'"
            )
            return candidate, fallback_model
        raise ValueError(f"No {kind} provider available for fallback")

    @classmethod
    def get_llm_client(cls) -> BaseLLMClient:
        """Get the configured LLM client, with fallback if the provider is unavailable (#568)."""
        if cls._llm_client is not None:
            return cls._llm_client

        provider, model = cls.parse_model_string(settings.llm_model)
        provider = provider.lower()
        available = settings.available_providers
        logger.info(f"Creating LLM client: provider={provider}, model={model}, available={available}")

        if provider not in available:
            provider, model = cls._resolve_fallback("llm", provider, model)

        cls._llm_client = cls._create_llm_client(provider, model)
        cls._llm_provider_used = provider
        cls._llm_model_used = model
        return cls._llm_client

    @classmethod
    def get_embedding_client(cls) -> EmbeddingClient:
        """Get the configured embedding client, with fallback if the provider is unavailable (#568)."""
        if cls._embedding_client is not None:
            return cls._embedding_client

        provider, model = cls.parse_model_string(settings.embedding_model)
        provider = provider.lower()
        available = settings.available_providers

        if provider not in available:
            provider, model = cls._resolve_fallback("embedding", provider, model)
        elif provider in _NO_EMBEDDING_PROVIDERS:
            logger.warning(f"Provider {provider} doesn't support embeddings, using fallback")
            provider, model = cls._resolve_fallback("embedding", provider, model)

        cls._embedding_client = cls._create_embedding_client(provider, model)
        cls._embedding_provider_used = provider
        cls._embedding_model_used = model
        return cls._embedding_client

    @classmethod
    def get_active_providers(cls) -> dict[str, dict | None]:
        """Return the actual provider+model used after fallback (for /health)."""
        return {
            "llm": (
                {"provider": cls._llm_provider_used, "model": cls._llm_model_used}
                if cls._llm_provider_used
                else None
            ),
            "embedding": (
                {"provider": cls._embedding_provider_used, "model": cls._embedding_model_used}
                if cls._embedding_provider_used
                else None
            ),
        }

    @classmethod
    def reset(cls):
        """Reset cached clients (useful for testing)."""
        cls._llm_client = None
        cls._embedding_client = None
        cls._llm_provider_used = None
        cls._embedding_provider_used = None
        cls._llm_model_used = None
        cls._embedding_model_used = None


def get_llm_client() -> BaseLLMClient:
    return ClientFactory.get_llm_client()


def get_embedding_client() -> EmbeddingClient:
    return ClientFactory.get_embedding_client()
