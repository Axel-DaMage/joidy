from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    database_url: str = "sqlite:////data/db/joidy.db"
    app_env: str = "development"

    # Gemini model IDs
    llm_model: str = "gemini-2.0-flash"
    embedding_model: str = "models/text-embedding-004"

    # Rate limiting (free tier: 15 RPM)
    max_requests_per_minute: int = 12  # Conservative, below 15 RPM limit


settings = Settings()
