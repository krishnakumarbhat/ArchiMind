"""Pydantic v2 application settings (env-driven, no hardcoded secrets)."""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the ArchiMind engine."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    documentation_model: str = Field(default="gemini-3.1-flash-lite-preview", alias="DOCUMENTATION_MODEL")
    chat_model: str = Field(default="gemini-3.1-flash-lite-preview", alias="CHAT_MODEL")
    embedding_model: str = Field(default="models/gemini-embedding-001", alias="EMBEDDING_MODEL")
    max_concurrent_jobs: int = Field(default=1, alias="MAX_CONCURRENT_JOBS")
    data_path: str = Field(default="data", alias="DATA_PATH")
    golden_cache_path: str = Field(default="data/golden", alias="GOLDEN_CACHE_PATH")
    tarball_max_mb: int = Field(default=60, alias="TARBALL_MAX_MB")
    tarball_max_files: int = Field(default=400, alias="TARBALL_MAX_FILES")
    tarball_timeout_s: int = Field(default=60, alias="TARBALL_TIMEOUT_S")
    mermaid_max_retries: int = Field(default=3, alias="MERMAID_MAX_RETRIES")


SETTINGS = Settings()  # ponytail: single shared instance; re-read env only at import
