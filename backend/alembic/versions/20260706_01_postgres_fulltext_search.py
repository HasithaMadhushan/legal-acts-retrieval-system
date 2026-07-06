"""add postgres full-text search columns (F-013)

Adds a generated `search_vector` tsvector column + GIN index to `legal_acts`
(title/category/source_name/raw_text) and `act_sections` (heading/text), so
`search_service.py` can use a real indexed full-text match (`@@`) instead of
an unindexed `ILIKE '%...%'` scan over these large text columns on Postgres.

This is Postgres-only DDL (generated columns + tsvector + GIN are not
portable to SQLite, which is what the test suite and local `create_all()`
dev path use). SQLite keeps working exactly as before -- `search_service.py`
falls back to the original ILIKE-based matching for that column whenever the
active database isn't Postgres, and this migration is a no-op there so
`alembic upgrade head` still succeeds against a SQLite database (see
`app/tests/test_migrations.py`).

Revision ID: 20260706_01
Revises: 20260705_01
Create Date: 2026-07-06

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260706_01"
down_revision: str | None = "20260705_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        """
        ALTER TABLE legal_acts ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(category, '') || ' ' || coalesce(source_name, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(raw_text, '')), 'C')
        ) STORED
        """
    )
    op.execute(
        "CREATE INDEX ix_legal_acts_search_vector ON legal_acts USING GIN (search_vector)"
    )

    op.execute(
        """
        ALTER TABLE act_sections ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(heading, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(text, '')), 'B')
        ) STORED
        """
    )
    op.execute(
        "CREATE INDEX ix_act_sections_search_vector ON act_sections USING GIN (search_vector)"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute("DROP INDEX IF EXISTS ix_act_sections_search_vector")
    op.execute("ALTER TABLE act_sections DROP COLUMN IF EXISTS search_vector")
    op.execute("DROP INDEX IF EXISTS ix_legal_acts_search_vector")
    op.execute("ALTER TABLE legal_acts DROP COLUMN IF EXISTS search_vector")
