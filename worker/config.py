from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://joidy:joidy@postgres:5432/joidy"
    api_url: str = "http://api:8000"
    ai_service_url: str = "http://ai-service:8002"
    vault_path: str = "/vault"
    app_env: str = "development"
    auth_password: str | None = None
    # Local SQLite log of pending vault events, so events survive a worker
    # crash (kill -9 / OOM) and are replayed on next startup (#371).
    event_log_path: str = "/data/db/vault_events.db"
    # Grace period (seconds) used to pair a deleted file with an added file of
    # identical content, treating the pair as a rename instead of delete+create
    # (#364).
    rename_match_window: float = 1.0


settings = Settings()
