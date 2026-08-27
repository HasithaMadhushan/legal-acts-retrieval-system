from pathlib import Path

from sqlalchemy import create_engine, inspect

from app.db.migrate import run_migrations


def test_run_migrations_creates_full_schema_from_empty_database(tmp_path, monkeypatch):
    db_path = tmp_path / "migration_check.db"
    database_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        run_migrations()

        engine = create_engine(database_url)
        try:
            inspector = inspect(engine)
            table_names = set(inspector.get_table_names())
            section_columns = {column["name"] for column in inspector.get_columns("act_sections")}
            section_indexes = {index["name"] for index in inspector.get_indexes("act_sections")}
        finally:
            engine.dispose()
    finally:
        get_settings.cache_clear()

    assert {
        "users",
        "legal_acts",
        "act_sections",
        "legal_references",
        "processing_jobs",
        "saved_items",
        "evaluation_runs",
        "evaluation_gold_references",
        "password_reset_tokens",
        "reading_history_items",
        "llm_extraction_cache",
        "alembic_version",
    }.issubset(table_names)
    assert {
        "embedding",
        "embedding_provider",
        "embedding_model",
        "embedding_dimension",
        "embedding_source_hash",
        "embedding_status",
        "embedded_at",
        "embedding_error",
    }.issubset(section_columns)
    assert "ix_act_sections_embedding_status_model" in section_indexes
    assert "ix_act_sections_embedding_hnsw" not in section_indexes
    assert Path(db_path).exists()
