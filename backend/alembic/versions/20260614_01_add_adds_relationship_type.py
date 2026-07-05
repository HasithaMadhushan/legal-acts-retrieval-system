"""add ADDS relationship type

Revision ID: 20260614_01
Revises: 20260613_01
Create Date: 2026-06-14
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260614_01"
down_revision: str | None = "20260613_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE relationship_type ADD VALUE IF NOT EXISTS 'ADDS'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be dropped safely without rebuilding the enum.
    pass
