from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables directly from the SQLAlchemy models.

    Alembic (see `app.db.migrate.run_migrations`) is the source of truth for the
    application's runtime schema. This helper exists for tests only, where
    creating tables straight from the models is faster and simpler than running
    migrations for every test's database reset.
    """
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
