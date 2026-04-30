"""add trigram search indexes

Revision ID: search_trgm_20260430
Revises: 3c1e8d85825f
Create Date: 2026-04-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "search_trgm_20260430"
down_revision: Union[str, Sequence[str], None] = "3c1e8d85825f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_metadata_common_name_trgm "
        "ON metadata USING gin (common_name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_metadata_description_trgm "
        "ON metadata USING gin (description gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_metadata_full_description_trgm "
        "ON metadata USING gin (full_description gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_nodes_display_name_trgm "
        "ON nodes USING gin (display_name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_nodes_name_trgm "
        "ON nodes USING gin (name gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_nodes_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_nodes_display_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_metadata_full_description_trgm")
    op.execute("DROP INDEX IF EXISTS ix_metadata_description_trgm")
    op.execute("DROP INDEX IF EXISTS ix_metadata_common_name_trgm")
