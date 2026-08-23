from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DEV_SECRET_KEY = "change-this-development-secret"

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
    # Demo accounts are seeded only in development by default. Set
    # SEED_DEMO_DATA=true/false to override (e.g. a staging demo deployment).
    seed_demo_data: bool | None = None
    database_url: str = "sqlite:///./legal_acts.db"
    secret_key: str = DEFAULT_DEV_SECRET_KEY
    access_token_expire_minutes: int = 480
    remember_me_expire_minutes: int = 60 * 24 * 30
    frontend_url: str = "http://localhost:3000"
    password_reset_expire_minutes: int = 60
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 50
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    docling_enabled: bool = True
    docling_timeout_seconds: int = 60
    ocr_enabled: bool = False
    doc_parser_primary: str = "docling"
    # Alembic is the schema source of truth. The app runs migrations at startup so
    # local dev keeps "just works" behavior; tests disable this and manage the
    # schema directly via Base.metadata for speed and per-test isolation.
    auto_migrate_on_startup: bool = True
    log_level: str = "INFO"
    # "console" gives human-friendly colored output for local dev; "json" emits
    # one JSON object per line, suitable for ingestion by log aggregators.
    log_format: str = "console"
    # Error tracking (Sentry) is opt-in: leave unset to disable it entirely,
    # which is the correct default for local dev and tests.
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.0
    # Per-client-IP throttle on /auth/* to slow down credential-stuffing/brute-force
    # login attempts and mass account registration. Disabled only in tests, where
    # fixtures log in dozens of times per second from a single "client" IP.
    rate_limit_enabled: bool = True
    auth_rate_limit: str = "20/minute"
    # Object storage for uploaded PDFs. Leave unset (the default) to store
    # files on local disk under UPLOAD_DIR -- correct for a single-instance
    # deployment. Set S3_BUCKET to switch to S3 or an S3-compatible service
    # (Cloudflare R2, MinIO, ...); credentials come from the standard AWS
    # environment variables / instance role, not from app settings.
    s3_bucket: str | None = None
    s3_prefix: str = ""
    s3_endpoint_url: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def _guard_against_default_production_secret(self) -> "Settings":
        is_production = self.environment.strip().lower() == "production"
        if is_production and self.secret_key == DEFAULT_DEV_SECRET_KEY:
            raise RuntimeError(
                "Refusing to start with the default SECRET_KEY while ENVIRONMENT=production. "
                "Set a unique SECRET_KEY via environment variable or .env file."
            )

    @property
    def should_seed_demo_data(self) -> bool:
        """Explicit SEED_DEMO_DATA wins; otherwise seed in development only.

        Demo accounts ship well-known passwords (see app/db/seed.py), so they
        must never be (re)created outside development by accident.
        """
        if self.seed_demo_data is not None:
            return self.seed_demo_data
        return self.environment.strip().lower() == "development"
        return self

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
