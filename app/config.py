from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Video Archive API"
    app_env: str = "dev"
    transcription_provider: str = "mock"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="")


settings = Settings()
