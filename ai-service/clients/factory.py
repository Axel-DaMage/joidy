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

# Canonical LLM fallback order (#1460): the configured ``LLM_MODEL`` provider
# is always primary; the remaining *configured* providers are tried in this
# order. Ollama is intentionally last — it is the only fully-local provider
# (no API key, no external service) and therefore the final safety net.
_LLM_FALLBACK_ORDER = ["gemini", "openai", "anthropic", "openrouter", "cohere", "ollama"]

# Default chat model used when a provider only serves as a fallback (the
# primary always uses the model named in ``LLM_MODEL``).
_LLM_FALLBACK_MODELS = {
    "gemini": "gemini-2.0-flash",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-haiku-20240307",
    "openrouter": "openai/gpt-4o-mini",
    "cohere": "command-r",
    "ollama": _OLLAMA_LLM_FALLBACK_MODEL,
}


class ClientFactory:
    """Factory for creating LLM and embedding clients based on model configuration.

    The LLM client is a failover chain (#568, #1460): ``LLM_MODEL``'s provider
    first, then every other configured provider in ``_LLM_FALLBACK_ORDER``
    order, with Ollama last. Embedding clients keep a two-provider chain
    (primary → Ollama) because cross-provider vectors have incompatible
    dimensions — a wider chain would corrupt ``note_embeddings``.
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
    def _create_llm_client(cls, provider: str, model: str, config: dict) -> BaseLLMClient:
        """Instantiate a raw LLM client for the given provider."""
        if provider == "gemini":
            return GeminiClient(api_key=config["api_key"], model=model)
        elif provider == "openai":
            return OpenAIClient(api_key=config["api_key"], model=model, base_url=config.get("base_url", ""))
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
    def _create_embedding_client(cls, provider: str, model: str, config: dict) -> EmbeddingClient:
        """Instantiate a raw embedding client for the given provider."""
        if provider == "gemini":
            return GeminiClient(api_key=config["api_key"], model=model)
        elif provider == "openai":
            return OpenAIClient(
                api_key=config["api_key"],
                model=model,
                is_embedding=True,
                base_url=config.get("base_url", ""),
            )
        elif provider == "cohere":
            return CohereClient(api_key=config["api_key"], model=model, is_embedding=True)
        elif provider == "ollama":
            return OllamaClient(base_url=config["base_url"], model=model, is_embedding=True)
        elif provider in ("anthropic", "openrouter"):
            logger.warning(f"Provider {provider} doesn't have dedicated embedding, using Ollama fallback")
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

        When more than one provider is configured, wraps the chain in a
        FallbackLLMClient for automatic failover (#568, #1460).
        """
        if cls._llm_client is not None:
            return cls._llm_client

        provider, model = cls.parse_model_string(settings.llm_model)
        provider = provider.lower()

        available = settings.available_providers
        logger.info(f"Creating LLM client: provider={provider}, model={model}, available={available}")

        if provider not in available:
            raise ValueError(f"Provider '{provider}' not configured. Available: {available}")

        config = settings.provider_config[provider]
        chain = [cls._create_llm_client(provider, model, config)]

        # Build the fallback chain (#1460): every other configured provider in
        # _LLM_FALLBACK_ORDER order, Ollama always last. A provider whose client
        # fails to construct (bad config) is skipped so it cannot break the
        # whole chain.
        for fallback_provider in _LLM_FALLBACK_ORDER:
            if fallback_provider == provider or fallback_provider not in available:
                continue
            try:
                chain.append(
                    cls._create_llm_client(
                        fallback_provider,
                        _LLM_FALLBACK_MODELS[fallback_provider],
                        settings.provider_config[fallback_provider],
                    )
                )
            except Exception:
                logger.warning(
                    f"Skipping '{fallback_provider}' in the LLM fallback chain — client construction failed",
                    exc_info=True,
                )

        if len(chain) > 1:
            cls._llm_client = FallbackLLMClient(primary=chain[0], fallbacks=chain[1:])
            logger.info(f"LLM fallback chain: {' -> '.join(c.provider_name for c in chain)}")
        else:
            cls._llm_client = chain[0]

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
            raise ValueError(f"Provider '{provider}' not configured. Available: {available}")

        config = settings.provider_config[provider]
        primary = cls._create_embedding_client(provider, model, config)

        # Wrap with Ollama fallback if primary is not Ollama and Ollama is available.
        # Skip if primary is already Ollama (e.g. anthropic/openrouter embedding fallback).
        if provider != "ollama" and "ollama" in available and not isinstance(primary, OllamaClient):
            ollama_config = settings.provider_config["ollama"]
            secondary = OllamaClient(
                base_url=ollama_config["base_url"],
                model=_OLLAMA_EMB_FALLBACK_MODEL,
                is_embedding=True,
            )
            cls._embedding_client = FallbackEmbeddingClient(primary=primary, secondary=secondary)
            logger.info(f"Embedding client wrapped with Ollama fallback (primary={provider}, secondary=ollama)")
        else:
            cls._embedding_client = primary

        return cls._embedding_client

    @classmethod
    async def aclose(cls) -> None:
        """Close cached clients and release their connections (#998).

        Provider clients hold reusable sessions (aiohttp.ClientSession for
        Ollama/OpenRouter, httpx clients inside the OpenAI/Anthropic SDKs).
        Called from the FastAPI lifespan on shutdown so nothing is left
        unclosed; the cache is reset so a later get_*_client() creates
        fresh instances.
        """
        for client in (cls._llm_client, cls._embedding_client):
            if client is None:
                continue
            try:
                await client.close()
            except Exception:
                logger.exception(f"Error closing AI client '{client.provider_name}'")
        cls.reset()

    @classmethod
    def reset(cls):
        """Reset cached clients (useful for testing)."""
        cls._llm_client = None
        cls._embedding_client = None


async def aclose_clients() -> None:
    await ClientFactory.aclose()


def get_llm_client() -> BaseLLMClient:
    return ClientFactory.get_llm_client()


def get_embedding_client() -> EmbeddingClient:
    return ClientFactory.get_embedding_client()
