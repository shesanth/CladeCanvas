"""add metadata provenance fields

Revision ID: 8f7c1b2a4d5e
Revises: 3c1e8d85825f
Create Date: 2026-04-30 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8f7c1b2a4d5e"
down_revision: Union[str, Sequence[str], None] = "3c1e8d85825f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "metadata",
        sa.Column(
            "source_label",
            sa.Text(),
            nullable=False,
            server_default="Wikidata/Wikipedia",
        ),
    )
    op.add_column("metadata", sa.Column("source_url", sa.Text(), nullable=True))
    op.add_column("metadata", sa.Column("source_match_method", sa.Text(), nullable=True))
    op.add_column("metadata", sa.Column("enriched_at", sa.DateTime(), nullable=True))
    op.add_column(
        "metadata",
        sa.Column(
            "provenance_confidence",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "metadata",
        sa.Column(
            "field_sources",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )

    op.execute("UPDATE metadata SET enriched_at = last_updated WHERE enriched_at IS NULL")
    op.execute(
        "UPDATE metadata SET provenance_confidence = COALESCE(enriched_score, 0) "
        "WHERE provenance_confidence = 0"
    )
    op.execute(
        "UPDATE metadata SET source_url = 'https://www.wikidata.org/wiki/' || wikidata_q "
        "WHERE source_url IS NULL AND wikidata_q IS NOT NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("metadata", "field_sources")
    op.drop_column("metadata", "provenance_confidence")
    op.drop_column("metadata", "enriched_at")
    op.drop_column("metadata", "source_match_method")
    op.drop_column("metadata", "source_url")
    op.drop_column("metadata", "source_label")
