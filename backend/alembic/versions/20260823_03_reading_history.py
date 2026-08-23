"""add reading history items

Revision ID: 20260823_03
Revises: 20260823_02
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260823_03"
down_revision: str | None = "20260823_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reading_history_items",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column(
            "item_type",
            sa.Enum("ACT", "SECTION", name="reading_history_item_type"),
            nullable=False,
        ),
        sa.Column("act_id", sa.String(length=36), nullable=False),
        sa.Column("section_id", sa.String(length=36), nullable=True),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["act_id"], ["legal_acts.id"]),
        sa.ForeignKeyConstraint(["section_id"], ["act_sections.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reading_history_items_act_id"),
        "reading_history_items",
        ["act_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reading_history_items_section_id"),
        "reading_history_items",
        ["section_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reading_history_items_user_id"),
        "reading_history_items",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_reading_history_items_user_id"), table_name="reading_history_items")
    op.drop_index(op.f("ix_reading_history_items_section_id"), table_name="reading_history_items")
    op.drop_index(op.f("ix_reading_history_items_act_id"), table_name="reading_history_items")
    op.drop_table("reading_history_items")
    op.execute("DROP TYPE IF EXISTS reading_history_item_type")
