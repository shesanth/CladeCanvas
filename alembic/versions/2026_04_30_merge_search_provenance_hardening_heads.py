"""merge search, provenance, and hardening migration heads

Revision ID: merge_20260430_heads
Revises: search_trgm_20260430, 8f7c1b2a4d5e, 6f2d9a7b1c3e
Create Date: 2026-04-30 00:00:00.000000

"""
from typing import Sequence, Union


revision: str = "merge_20260430_heads"
down_revision: Union[str, Sequence[str], None] = (
    "search_trgm_20260430",
    "8f7c1b2a4d5e",
    "6f2d9a7b1c3e",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge migration heads."""
    pass


def downgrade() -> None:
    """Unmerge migration heads."""
    pass
