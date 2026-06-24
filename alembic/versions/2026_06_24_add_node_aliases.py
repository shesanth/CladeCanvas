"""add node aliases

Revision ID: node_aliases_20260624
Revises: merge_20260430_heads
Create Date: 2026-06-24 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "node_aliases_20260624"
down_revision: Union[str, Sequence[str], None] = (
    "merge_20260430_heads"
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "node_aliases",
        sa.Column(
            "alias_node_id",
            sa.Text(),
            sa.ForeignKey("nodes.node_id"),
            primary_key=True,
        ),
        sa.Column(
            "canonical_node_id",
            sa.Text(),
            sa.ForeignKey("nodes.node_id"),
            nullable=False,
        ),
        sa.Column(
            "reason",
            sa.Text(),
            nullable=False,
            server_default="canonical_alias",
        ),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=False,
            server_default="1",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_node_aliases_canonical_node_id",
        "node_aliases",
        ["canonical_node_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_node_aliases_canonical_node_id", table_name="node_aliases")
    op.drop_table("node_aliases")
