from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:////data/db/joidy.db"
    api_url: str = "http://api:8000"
    ai_service_url: str = "http://ai-service:8002"
    vault_path: str = "/vault"
    app_env: str = "development"


settings = Settings()
