"""add extraction artifact pointer columns on legal_acts

Revision ID: 20260827_01
Revises: 20260825_01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260827_01"
down_revision: str | None = "20260825_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("legal_acts", sa.Column("extraction_artifact_key", sa.String(length=1000)))
    op.add_column("legal_acts", sa.Column("extraction_artifact_sha256", sa.String(length=64)))
    op.add_column("legal_acts", sa.Column("extraction_schema_version", sa.String(length=32)))
    op.add_column("legal_acts", sa.Column("extraction_created_at", sa.DateTime()))


def downgrade() -> None:
    op.drop_column("legal_acts", "extraction_created_at")
    op.drop_column("legal_acts", "extraction_schema_version")
    op.drop_column("legal_acts", "extraction_artifact_sha256")
    op.drop_column("legal_acts", "extraction_artifact_key")
