"""add lawyer request fields and password reset tokens

Revision ID: 20260823_01
Revises: 20260706_01
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260823_01"
down_revision: str | None = "20260706_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "lawyer_request_status",
            sa.String(length=32),
            nullable=False,
            server_default="none",
        ),
    )
    op.add_column("users", sa.Column("enrollment_number", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("enrollment_proof_path", sa.String(length=500), nullable=True))
    op.create_index(
        op.f("ix_users_lawyer_request_status"),
        "users",
        ["lawyer_request_status"],
        unique=False,
    )
    op.create_table(
        "password_reset_tokens",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_password_reset_tokens_user_id"),
        "password_reset_tokens",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_password_reset_tokens_token_hash"),
        "password_reset_tokens",
        ["token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_password_reset_tokens_token_hash"), table_name="password_reset_tokens")
    op.drop_index(op.f("ix_password_reset_tokens_user_id"), table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index(op.f("ix_users_lawyer_request_status"), table_name="users")
    op.drop_column("users", "enrollment_proof_path")
    op.drop_column("users", "enrollment_number")
    op.drop_column("users", "lawyer_request_status")
