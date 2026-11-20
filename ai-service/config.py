import ipaddress
import logging
from urllib.parse import urlparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Host-gateway aliases that resolve to the local machine from inside a
# container — http:// traffic to these never leaves the host.
_LOOPBACK_HOSTNAMES = {
    "localhost",
    "host.docker.internal",  # Docker (see .env.example OLLAMA_BASE_URL)
    "host.containers.internal",  # Podman equivalent
}


def _is_loopback_host(hostname: str) -> bool:
    """True when the hostname can only resolve to the local machine."""
    host = hostname.strip().rstrip(".").lower()
    if host in _LOOPBACK_HOSTNAMES or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback  # 127.0.0.0/8, ::1
    except ValueError:
        return False


def validate_base_url(url: str, *, name: str = "base_url", allow_insecure: bool = False) -> str:
    """Validate a provider base URL and return it normalized (no trailing /).

    Policy (#1330):
    - ``https://`` is required for remote hosts — cleartext http to a remote
      host would expose note content and provider API keys.
    - ``http://`` is allowed only for loopback targets (localhost,
      *.localhost, 127.0.0.0/8, ::1 and the Docker/Podman host-gateway
      aliases) since e.g. Ollama is expected to run on the local machine.

    Raises ValueError on rejection unless ``allow_insecure`` is set, which
    downgrades the refusal to a loud warning (explicit operator opt-in —
    e.g. Ollama in a sibling container on a private docker network).
    """
    cleaned = url.strip()
    try:
        parsed = urlparse(cleaned)
        hostname = parsed.hostname
        _ = parsed.port  # raises ValueError on malformed ports
    except ValueError:
        parsed, hostname = None, None

    reason = None
    if parsed is None or not parsed.scheme:
        reason = "missing URL scheme — expected 'https://' or 'http://'"
    else:
        scheme = parsed.scheme.lower()
        if scheme == "https":
            if not hostname:
                reason = "missing host"
        elif scheme == "http":
            if not hostname:
                reason = "missing host"
            elif not _is_loopback_host(hostname):
                reason = "http:// is only allowed for loopback hosts"
        else:
            reason = f"unsupported scheme '{parsed.scheme}' — expected 'https://' or 'http://'"

    if reason is not None:
        msg = f"Invalid {name} {cleaned!r}: {reason}."
        if allow_insecure:
            logger.warning(f"{msg} ALLOW_INSECURE_BASE_URLS is enabled — accepting anyway.")
            return cleaned.rstrip("/")
        raise ValueError(
            f"{msg} Remote hosts must use https://; http:// is only allowed for loopback "
            "targets (localhost, *.localhost, 127.0.0.0/8, ::1, host.docker.internal, "
            "host.containers.internal). Set ALLOW_INSECURE_BASE_URLS=true to override."
        )
    return cleaned.rstrip("/")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+psycopg2://joidy:joidy@postgres:5432/joidy"
    app_env: str = "development"

    # Internal auth: shared secret for API → ai-service communication
    internal_secret: str = ""

    # CORS
    cors_allowed_origins: str = ""

    # Multi-provider API keys
    gemini_api_key: str = ""
    openai_api_key: str = ""
    # Optional custom base URL for the OpenAI provider (OpenAI-compatible
    # routers such as standardcompute, LiteLLM, vLLM, OpenRouter-style proxies).
    openai_base_url: str = ""
    anthropic_api_key: str = ""
    openrouter_api_key: str = ""
    cohere_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # Security: provider base-URL policy (#1330). http:// is only accepted
    # for loopback targets; remote hosts must use https://. Setting
    # ALLOW_INSECURE_BASE_URLS=true downgrades the startup refusal to a
    # warning — needed e.g. when Ollama runs in a sibling container
    # (OLLAMA_BASE_URL=http://ollama:11434 on a private docker network).
    allow_insecure_base_urls: bool = False
    # Optional explicit proxy for provider HTTP clients. httpx-based SDK
    # transports are built with trust_env=False so ambient HTTP(S)_PROXY /
    # ALL_PROXY variables are ignored; set this when providers must egress
    # through a proxy.
    provider_proxy_url: str = ""

    # Model configuration (format: "provider:model" or just "model" for default provider)
    # Examples: "gemini:gemini-2.0-flash", "openai:gpt-4", "anthropic:claude-3-opus", "ollama:llama3"
    llm_model: str = "gemini:gemini-2.0-flash"
    embedding_model: str = "gemini:models/text-embedding-004"

    # Floor for max_tokens on LLM calls (0 = keep the endpoint's own value).
    # Reasoning routers (e.g. "standardcompute") spend max_tokens on hidden
    # reasoning before emitting content, so small budgets return null content.
    llm_max_tokens: int = 0

    # Rate limiting (free tier: 15 RPM)
    max_requests_per_minute: int = 12
    ai_retry_max_attempts: int = 5
    ai_retry_base_delay_seconds: float = 1.0
    ai_retry_max_delay_seconds: float = 30.0

    # Timeouts (seconds) for provider calls. Prevents indefinite hangs when a
    # provider is degraded or unreachable. Embeddings are usually fast; LLM
    # generation can take longer.
    embed_timeout: float = 30.0
    llm_timeout: float = 60.0
    # Connect timeout shared by all providers (time to establish the TCP link).
    connect_timeout: float = 5.0

    # Response cache: avoids re-calling providers for identical inputs.
    cache_ttl_seconds: float = 3600.0
    cache_max_size: int = 2048

    @model_validator(mode="after")
    def _validate_provider_base_urls(self) -> "Settings":
        """Refuse to start on insecure/malformed provider base URLs (#1330).

        Runs at Settings() construction (module import) so a tampered env
        fails fast instead of silently exfiltrating note content.
        """
        for env_name, url in (
            ("OPENAI_BASE_URL", self.openai_base_url),
            ("OLLAMA_BASE_URL", self.ollama_base_url),
        ):
            if url:
                validate_base_url(url, name=env_name, allow_insecure=self.allow_insecure_base_urls)
        return self

    @property
    def provider_config(self) -> dict:
        """Returns dict of provider -> {api_key, base_url} for available providers."""
        config = {}
        if self.gemini_api_key:
            config["gemini"] = {"api_key": self.gemini_api_key}
        if self.openai_api_key:
            client = {"api_key": self.openai_api_key}
            if self.openai_base_url:
                client["base_url"] = self.openai_base_url
            config["openai"] = client
        if self.anthropic_api_key:
            config["anthropic"] = {"api_key": self.anthropic_api_key}
        if self.openrouter_api_key:
            config["openrouter"] = {"api_key": self.openrouter_api_key}
        if self.cohere_api_key:
            config["cohere"] = {"api_key": self.cohere_api_key}
        if self.ollama_base_url:
            config["ollama"] = {"base_url": self.ollama_base_url}
        return config

    @property
    def available_providers(self) -> list[str]:
        return list(self.provider_config.keys())

    def _model_provider(self, model: str) -> str:
        """Extract the provider prefix from a 'provider:model' string."""
        if ":" in model:
            return model.split(":", 1)[0].lower()
        return "gemini"

    @property
    def llm_provider(self) -> str:
        return self._model_provider(self.llm_model)

    @property
    def embedding_provider(self) -> str:
        return self._model_provider(self.embedding_model)

    @property
    def is_llm_configured(self) -> bool:
        """True when the configured LLM provider is actually available."""
        return self.llm_provider in self.available_providers

    @property
    def is_embedding_configured(self) -> bool:
        """True when the configured embedding provider is actually available."""
        return self.embedding_provider in self.available_providers

    @property
    def is_ai_enabled(self) -> bool:
        """True only when the *configured* providers are available, not just any provider (#642)."""
        return self.is_llm_configured and self.is_embedding_configured


settings = Settings()
