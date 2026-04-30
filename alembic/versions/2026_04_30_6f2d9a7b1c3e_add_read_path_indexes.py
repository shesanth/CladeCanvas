"""add read path indexes

Revision ID: 6f2d9a7b1c3e
Revises: 3c1e8d85825f
Create Date: 2026-04-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "6f2d9a7b1c3e"
down_revision: Union[str, Sequence[str], None] = "3c1e8d85825f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_nodes_parent_node_id", "nodes", ["parent_node_id"], unique=False)
    op.create_index("ix_metadata_common_name", "metadata", ["common_name"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_metadata_common_name", table_name="metadata")
    op.drop_index("ix_nodes_parent_node_id", table_name="nodes")

