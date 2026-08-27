from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, inspect, text

from alembic import command
from alembic.config import Config

BACKEND_DIR = Path(__file__).resolve().parents[2]
MIGRATION_PATH = BACKEND_DIR / "alembic" / "versions" / "20260828_01_native_pgvector_embeddings.py"
HNSW_INDEX_SQL = """
CREATE INDEX ix_act_sections_embedding_hnsw
ON act_sections
USING hnsw (embedding vector_cosine_ops)
WHERE embedding IS NOT NULL;
""".strip()
HASH_VECTOR_JSON = "[0.11, 0.22, 0.33]"
PRE_PGVECTOR_REVISION = "20260827_01"


def _alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _prepare_settings(monkeypatch, database_url: str):
    monkeypatch.setenv("DATABASE_URL", database_url)
    from app.core.config import get_settings

    get_settings.cache_clear()
    return get_settings


def _insert_section_with_hash_embedding(engine, *, section_id: str) -> None:
    now = "2026-08-01 12:00:00"
    act_id = str(uuid4())
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO legal_acts (
                    id, title, normalized_title, source_file_name, stored_file_path,
                    file_sha256, processing_status, parser_used, uploaded_at,
                    created_at, updated_at
                ) VALUES (
                    :act_id, :title, :title, :file_name, :file_name,
                    :file_sha256, 'VERIFIED', 'PYMUPDF', :now, :now, :now
                )
                """
            ),
            {
                "act_id": act_id,
                "title": "Hash Vector Act",
                "file_name": "hash-vector.pdf",
                "file_sha256": uuid4().hex.ljust(64, "0")[:64],
                "now": now,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO act_sections (
                    id, act_id, section_number, section_type, text, normalized_text,
                    sort_order, verification_status, embedding, created_at, updated_at
                ) VALUES (
                    :section_id, :act_id, '1', 'SECTION', :body, :body,
                    1, 'PENDING', :embedding, :now, :now
                )
                """
            ),
            {
                "section_id": section_id,
                "act_id": act_id,
                "body": "Existing hash embedding must be discarded.",
                "embedding": HASH_VECTOR_JSON,
                "now": now,
            },
        )


def test_pgvector_migration_declares_expected_identity_and_hnsw_sql():
    source = MIGRATION_PATH.read_text()
    assert 'revision: str = "20260828_01"' in source
    assert 'down_revision: str | None = "20260827_01"' in source
    assert "CREATE EXTENSION IF NOT EXISTS vector" in source
    assert "vector(384)" in source
    assert HNSW_INDEX_SQL in source
    assert "ix_act_sections_embedding_status_model" in source
    assert "postgresql.ENUM" in source
    assert "create_type=False" in source


def test_sqlite_upgrade_discards_hash_embeddings_and_marks_pending(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'pgvector_sqlite.db'}"
    get_settings = _prepare_settings(monkeypatch, database_url)
    section_id = str(uuid4())
    config = _alembic_config(database_url)
    engine = create_engine(database_url)
    try:
        command.upgrade(config, PRE_PGVECTOR_REVISION)
        _insert_section_with_hash_embedding(engine, section_id=section_id)
        command.upgrade(config, "head")

        inspector = inspect(engine)
        columns = {column["name"]: column for column in inspector.get_columns("act_sections")}
        indexes = {index["name"]: index for index in inspector.get_indexes("act_sections")}
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT embedding, embedding_status, embedding_provider, embedding_model
                    FROM act_sections
                    WHERE id = :section_id
                    """
                ),
                {"section_id": section_id},
            ).one()
            version = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
    finally:
        engine.dispose()
        get_settings.cache_clear()

    assert version == "20260828_01"
    assert row.embedding is None
    assert row.embedding_status == "PENDING"
    assert row.embedding_provider is None
    assert row.embedding_model is None
    assert "embedding" in columns
    assert columns["embedding"]["type"].__class__.__name__ != "VECTOR"
    assert "ix_act_sections_embedding_status_model" in indexes
    assert indexes["ix_act_sections_embedding_status_model"]["column_names"] == [
        "embedding_status",
        "embedding_model",
    ]
    assert "ix_act_sections_embedding_hnsw" not in indexes


def test_sqlite_downgrade_restores_json_embedding_storage(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'pgvector_sqlite_downgrade.db'}"
    get_settings = _prepare_settings(monkeypatch, database_url)
    section_id = str(uuid4())
    config = _alembic_config(database_url)
    engine = create_engine(database_url)
    try:
        command.upgrade(config, PRE_PGVECTOR_REVISION)
        _insert_section_with_hash_embedding(engine, section_id=section_id)
        command.upgrade(config, "head")
        command.downgrade(config, PRE_PGVECTOR_REVISION)

        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("act_sections")}
        indexes = {index["name"] for index in inspector.get_indexes("act_sections")}
        with engine.connect() as connection:
            embedding = connection.execute(
                text("SELECT embedding FROM act_sections WHERE id = :section_id"),
                {"section_id": section_id},
            ).scalar_one()
    finally:
        engine.dispose()
        get_settings.cache_clear()

    assert "embedding" in columns
    assert "embedding_status" not in columns
    assert "embedding_provider" not in columns
    assert "ix_act_sections_embedding_status_model" not in indexes
    assert embedding is None
