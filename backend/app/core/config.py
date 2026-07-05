from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

LEGAL_DISCLAIMER = (
    "This system is an academic research prototype for legal information retrieval support "
    "only. It does not provide legal advice, legal opinions, authoritative legal "
    "interpretation, or legally authoritative consolidation of Acts. Users must verify legal "
    "material using official sources and qualified legal professionals where required."
)

NO_LEGAL_ADVICE_MESSAGE = (
    "This system cannot provide legal advice, legal opinions, or personalized legal guidance. "
    "Use search only to retrieve potentially relevant legal materials and verify them through "
    "official sources or qualified legal professionals."
)


class Settings(BaseSettings):
    app_name: str = "Automated Legal Acts Retrieval System"
    environment: str = "development"
    database_url: str = "sqlite:///./legal_acts.db"
    secret_key: str = "change-this-development-secret"
    access_token_expire_minutes: int = 480
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 50
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    docling_enabled: bool = True
    docling_timeout_seconds: int = 60
    ocr_enabled: bool = False
    doc_parser_primary: str = "docling"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir)

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
