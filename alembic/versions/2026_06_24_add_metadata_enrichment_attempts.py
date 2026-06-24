"""add metadata enrichment attempts

Revision ID: enrichment_attempts_20260624
Revises: node_aliases_20260624
Create Date: 2026-06-24 13:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "enrichment_attempts_20260624"
down_revision: Union[str, Sequence[str], None] = "node_aliases_20260624"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "metadata_enrichment_attempts",
        sa.Column("node_id", sa.Text(), sa.ForeignKey("nodes.node_id"), primary_key=True),
        sa.Column("ott_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempted_at", sa.DateTime(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("last_provider", sa.Text(), nullable=True),
        sa.Column("last_match_method", sa.Text(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_metadata_enrichment_attempts_status",
        "metadata_enrichment_attempts",
        ["status"],
    )
    op.create_index(
        "ix_metadata_enrichment_attempts_next_retry_at",
        "metadata_enrichment_attempts",
        ["next_retry_at"],
    )
    op.create_index(
        "ix_metadata_enrichment_attempts_ott_id",
        "metadata_enrichment_attempts",
        ["ott_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_metadata_enrichment_attempts_ott_id", table_name="metadata_enrichment_attempts")
    op.drop_index("ix_metadata_enrichment_attempts_next_retry_at", table_name="metadata_enrichment_attempts")
    op.drop_index("ix_metadata_enrichment_attempts_status", table_name="metadata_enrichment_attempts")
    op.drop_table("metadata_enrichment_attempts")
