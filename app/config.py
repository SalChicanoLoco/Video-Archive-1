from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Video Archive API"
    app_env: str = "dev"
    transcription_provider: str = "mock"
    log_level: str = "INFO"
    provider_plugins: str = ""
    job_store_backend: str = "memory"
    sqlite_db_path: str = "data/jobs.db"
    app_port: int = 8000
    api_key: str = ""

    # Airtable
    airtable_api_key: str = ""
    airtable_base_id: str = ""
    airtable_table_tapes: str = "Tapes"
    airtable_table_transcripts: str = "Transcripts"
    airtable_table_edls: str = "EDLs"
    airtable_table_log: str = "Operation Log"

    # Anthropic
    anthropic_api_key: str = ""

    # Whisper
    whisper_model: str = "large-v3"

    # Directories
    input_dir: str = "/app/input"
    output_dir: str = "/app/output"
    models_dir: str = "/opt/whisper_cache"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="")


settings = Settings()
