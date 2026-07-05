"""Programmatic Alembic migration runner.

Alembic is the single source of truth for the database schema. This module lets
the app run `alembic upgrade head` at startup (so `uvicorn app.main:app` still
"just works" for local development against a fresh SQLite file, matching the
old create_all()-based experience) while keeping migrations authoritative for
Docker/production deployments as well.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from app.core.config import get_settings

# backend/app/db/migrate.py -> backend/
_BACKEND_DIR = Path(__file__).resolve().parents[2]


def run_migrations() -> None:
    settings = get_settings()
    alembic_cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(alembic_cfg, "head")
