from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Video Archive API"
    app_env: str = "dev"
    transcription_provider: str = "mock"
    log_level: str = "INFO"
    provider_plugins: str = ""
    job_store_backend: str = "memory"
    sqlite_db_path: str = "data/jobs.db"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="")


settings = Settings()
