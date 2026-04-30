from sqlalchemy import (
    MetaData, Table, Column, Index, Integer, Text, ForeignKey, DateTime, Float,
    text,
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
Index(
    "ix_metadata_common_name_trgm",
    metadata_table.c.common_name,
    postgresql_using="gin",
    postgresql_ops={"common_name": "gin_trgm_ops"},
)
Index(
    "ix_metadata_description_trgm",
    metadata_table.c.description,
    postgresql_using="gin",
    postgresql_ops={"description": "gin_trgm_ops"},
)
Index(
    "ix_metadata_full_description_trgm",
    metadata_table.c.full_description,
    postgresql_using="gin",
    postgresql_ops={"full_description": "gin_trgm_ops"},
)
Index(
    "ix_nodes_display_name_trgm",
    nodes.c.display_name,
    postgresql_using="gin",
    postgresql_ops={"display_name": "gin_trgm_ops"},
)
Index(
    "ix_nodes_name_trgm",
    nodes.c.name,
    postgresql_using="gin",
    postgresql_ops={"name": "gin_trgm_ops"},
)


def initialize_postgres_db():
    """Create tables and indexes if they don't exist. Idempotent."""
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    metadata.create_all(engine)
    print("Tables created.")
