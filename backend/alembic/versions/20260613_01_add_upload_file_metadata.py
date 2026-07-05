"""add upload file metadata

Revision ID: 20260613_01
Revises:
Create Date: 2026-06-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260613_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("legal_acts", sa.Column("file_size", sa.Integer(), nullable=True))
    op.add_column("legal_acts", sa.Column("mime_type", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("legal_acts", "mime_type")
    op.drop_column("legal_acts", "file_size")
