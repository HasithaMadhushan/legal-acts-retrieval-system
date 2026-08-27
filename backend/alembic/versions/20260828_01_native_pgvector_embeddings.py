"""migrate section embeddings to native pgvector

Existing JSON embeddings were hash-generated and must not be converted into
production vectors. PostgreSQL discards them, stores native vector(384) values,
and marks all sections PENDING for real-model backfill. SQLite keeps JSON
storage (no HNSW) while receiving the same metadata columns and PENDING
semantics.

Revision ID: 20260828_01
Revises: 20260827_01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260828_01"
down_revision: str | None = "20260827_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HNSW_INDEX_SQL = """
CREATE INDEX ix_act_sections_embedding_hnsw
ON act_sections
USING hnsw (embedding vector_cosine_ops)
WHERE embedding IS NOT NULL;
"""
STATUS_MODEL_INDEX_NAME = "ix_act_sections_embedding_status_model"
EMBEDDING_STATUS_VALUES = ("PENDING", "READY", "FAILED", "STALE")
METADATA_COLUMN_NAMES = (
    "embedding_error",
    "embedded_at",
    "embedding_status",
    "embedding_source_hash",
    "embedding_dimension",
    "embedding_model",
    "embedding_provider",
)


def _embedding_status_type(*, create_type: bool) -> sa.Enum:
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.ENUM(
            *EMBEDDING_STATUS_VALUES,
            name="embedding_status",
            create_type=create_type,
        )
    return sa.Enum(*EMBEDDING_STATUS_VALUES, name="embedding_status")


def _metadata_columns() -> list[sa.Column]:
    return [
        sa.Column("embedding_provider", sa.String(length=64), nullable=True),
        sa.Column("embedding_model", sa.String(length=255), nullable=True),
        sa.Column("embedding_dimension", sa.Integer(), nullable=True),
        sa.Column("embedding_source_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "embedding_status",
            _embedding_status_type(create_type=False),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("embedded_at", sa.DateTime(), nullable=True),
        sa.Column("embedding_error", sa.Text(), nullable=True),
    ]


def _replace_json_embedding_with_vector() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
    op.drop_column("act_sections", "embedding")
    op.execute(sa.text("ALTER TABLE act_sections ADD COLUMN embedding vector(384) NULL"))


def _add_metadata_columns() -> None:
    bind = op.get_bind()
    columns = _metadata_columns()
    if bind.dialect.name == "postgresql":
        _embedding_status_type(create_type=True).create(bind, checkfirst=True)
        for column in columns:
            op.add_column("act_sections", column)
        return
    with op.batch_alter_table("act_sections") as batch_op:
        for column in columns:
            batch_op.add_column(column)


def _drop_metadata_columns() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for name in METADATA_COLUMN_NAMES:
            op.drop_column("act_sections", name)
        _embedding_status_type(create_type=False).drop(bind, checkfirst=True)
        return
    with op.batch_alter_table("act_sections") as batch_op:
        for name in METADATA_COLUMN_NAMES:
            batch_op.drop_column(name)


def _restore_json_embedding() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.drop_column("act_sections", "embedding")
    op.add_column("act_sections", sa.Column("embedding", sa.JSON(), nullable=True))


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        _replace_json_embedding_with_vector()
    _add_metadata_columns()
    op.execute(sa.text("UPDATE act_sections SET embedding = NULL, embedding_status = 'PENDING'"))
    if op.get_bind().dialect.name == "postgresql":
        op.execute(HNSW_INDEX_SQL)
    op.create_index(
        STATUS_MODEL_INDEX_NAME,
        "act_sections",
        ["embedding_status", "embedding_model"],
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text("DROP INDEX IF EXISTS ix_act_sections_embedding_hnsw"))
    op.drop_index(STATUS_MODEL_INDEX_NAME, table_name="act_sections")
    _drop_metadata_columns()
    _restore_json_embedding()
