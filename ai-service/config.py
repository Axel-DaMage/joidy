from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "sqlite:////data/db/joidy.db"
    app_env: str = "development"

    # Multi-provider API keys
    gemini_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    openrouter_api_key: str = ""
    cohere_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # Model configuration (format: "provider:model" or just "model" for default provider)
    # Examples: "gemini:gemini-2.0-flash", "openai:gpt-4", "anthropic:claude-3-opus", "ollama:llama3"
    llm_model: str = "gemini:gemini-2.0-flash"
    embedding_model: str = "gemini:models/text-embedding-004"

    # Rate limiting (free tier: 15 RPM)
    max_requests_per_minute: int = 12
    ai_retry_max_attempts: int = 5
    ai_retry_base_delay_seconds: float = 1.0
    ai_retry_max_delay_seconds: float = 30.0

    @property
    def provider_config(self) -> dict:
        """Returns dict of provider -> {api_key, base_url} for available providers."""
        config = {}
        if self.gemini_api_key:
            config["gemini"] = {"api_key": self.gemini_api_key}
        if self.openai_api_key:
            config["openai"] = {"api_key": self.openai_api_key}
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

    @property
    def is_ai_enabled(self) -> bool:
        return len(self.available_providers) > 0


settings = Settings()
