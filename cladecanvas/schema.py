from sqlalchemy import (
    MetaData, Table, Column, Index, Integer, Text, ForeignKey, DateTime, Float,
)
from cladecanvas.db import engine

metadata = MetaData()

nodes = Table(
    "nodes", metadata,
    Column("node_id", Text, primary_key=True),
    Column("ott_id", Integer, nullable=True),
    Column("name", Text, nullable=False),
    Column("parent_node_id", Text),
    Column("rank", Text),
    Column("child_count", Integer),
    Column("has_metadata", Integer),
    Column("num_tips", Integer, nullable=True),
    Column("display_name", Text, nullable=True),
)

metadata_table = Table(
    "metadata", metadata,
    Column("node_id", Text, ForeignKey("nodes.node_id"), primary_key=True),
    Column("ott_id", Integer, nullable=True),
    Column("wikidata_q", Text),
    Column("common_name", Text),
    Column("description", Text),
    Column("full_description", Text),
    Column("image_url", Text),
    Column("wiki_page_url", Text),
    Column("image_thumb", Text),
    Column("last_updated", DateTime),
    Column("enriched_score", Float),
)

# Partial unique indexes — expressed here so Alembic autogenerate can see them
Index("ix_nodes_ott_id", nodes.c.ott_id,
      unique=True, postgresql_where=nodes.c.ott_id.isnot(None))
Index("ix_metadata_ott_id", metadata_table.c.ott_id,
      unique=True, postgresql_where=metadata_table.c.ott_id.isnot(None))


def initialize_postgres_db():
    """Create tables and indexes if they don't exist. Idempotent."""
    metadata.create_all(engine)
    print("Tables created.")
