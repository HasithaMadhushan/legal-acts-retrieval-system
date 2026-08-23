"""llm extraction, embeddings, and integrity indexes

Revision ID: 20260823_04
Revises: 20260823_03
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260823_04"
down_revision: str | None = "20260823_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_names(table: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}


def _ensure_index(name: str, table: str, columns: list[str], *, unique: bool = False) -> None:
    if name not in _index_names(table):
        op.create_index(name, table, columns, unique=unique)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "llm_extraction_cache" not in inspector.get_table_names():
        op.create_table(
            "llm_extraction_cache",
            sa.Column("content_hash", sa.String(length=64), primary_key=True),
            sa.Column("response_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    section_columns = {column["name"] for column in inspector.get_columns("act_sections")}
    if "embedding" not in section_columns:
        op.add_column("act_sections", sa.Column("embedding", sa.JSON(), nullable=True))

    _ensure_index("ix_legal_acts_uploaded_at", "legal_acts", ["uploaded_at"])
    _ensure_index("ix_legal_references_created_at", "legal_references", ["created_at"])
    _ensure_index("ix_processing_jobs_created_at", "processing_jobs", ["created_at"])
    _ensure_index(
        "ix_reading_history_items_user_viewed_at",
        "reading_history_items",
        ["user_id", "viewed_at"],
    )
    _ensure_index("ix_saved_items_act_id", "saved_items", ["act_id"])
    _ensure_index("ix_saved_items_section_id", "saved_items", ["section_id"])
    _ensure_index("ix_saved_items_reference_id", "saved_items", ["reference_id"])
    _ensure_index(
        "uq_saved_items_identity",
        "saved_items",
        ["user_id", "item_type", "act_id", "section_id", "reference_id"],
        unique=True,
    )
    _ensure_index(
        "uq_reading_history_identity",
        "reading_history_items",
        ["user_id", "item_type", "act_id", "section_id"],
        unique=True,
    )

    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute(
            """
            DO $$ BEGIN
              ALTER TYPE extraction_method ADD VALUE 'LLM';
            EXCEPTION
              WHEN duplicate_object THEN NULL;
            END $$;
            """
        )


def downgrade() -> None:
    for name, table in (
        ("uq_reading_history_identity", "reading_history_items"),
        ("uq_saved_items_identity", "saved_items"),
        ("ix_saved_items_reference_id", "saved_items"),
        ("ix_saved_items_section_id", "saved_items"),
        ("ix_saved_items_act_id", "saved_items"),
        ("ix_reading_history_items_user_viewed_at", "reading_history_items"),
        ("ix_processing_jobs_created_at", "processing_jobs"),
        ("ix_legal_references_created_at", "legal_references"),
        ("ix_legal_acts_uploaded_at", "legal_acts"),
    ):
        if name in _index_names(table):
            op.drop_index(name, table_name=table)
    inspector = sa.inspect(op.get_bind())
    if "embedding" in {column["name"] for column in inspector.get_columns("act_sections")}:
        op.drop_column("act_sections", "embedding")
    if "llm_extraction_cache" in inspector.get_table_names():
        op.drop_table("llm_extraction_cache")
