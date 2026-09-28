"""Environment-backed settings."""
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = ""
    gemini_api_key: str = ""
    app_environment: str = "development"
    llm_model: str = "gpt-4o-mini"
    llm_provider: str = "gemini"
    gemini_model: str = "gemini-3.8-flash"
    gemini_fallback_model: str = "gemini-3.6-flash,gemini-3.7-flash"
    embedding_model: str = "all-MiniLM-L6-v2"
    database_url: str = "postgresql+psycopg://requirements:requirements@127.0.0.1:5433/requirements_db"
    embedding_provider: str = "local"
    chroma_persist_directory: Path = REPO_ROOT / "backend" / "data" / "chroma"
    chroma_collection_name: str = "requirements_documents"
    frontend_origin: str = "http://localhost:5173"
    upload_directory: Path = REPO_ROOT / "backend" / "data" / "uploads"
    max_upload_size_mb: int = 20
    chunk_size: int = 1000
    chunk_overlap: int = 200

    @field_validator("chroma_persist_directory", mode="before")
    @classmethod
    def resolve_chroma_directory(cls, value):
        path = Path(value)
        return path if path.is_absolute() else (REPO_ROOT / path).resolve()


settings = Settings()
