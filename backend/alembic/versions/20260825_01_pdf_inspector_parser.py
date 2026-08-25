"""add PDF Inspector parser enum value

Revision ID: 20260825_01
Revises: 20260823_04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260825_01"
down_revision: str | None = "20260823_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE parser_name ADD VALUE IF NOT EXISTS 'PDF_INSPECTOR'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely while rows may use them.
    pass
