from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:////data/db/joidy.db"
    ai_service_url: str = "http://ai-service:8002"
    worker_url: str = "http://worker:8001"
    secret_key: str = "dev_secret_change_me"
    app_env: str = "development"
    github_token: str = ""
    github_username: str = ""


settings = Settings()
