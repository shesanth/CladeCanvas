from sqlalchemy import MetaData, Table, Column, Integer, Text, ForeignKey, DateTime, Float
from cladecanvas.db import engine

metadata = MetaData()

nodes = Table(
    "nodes", metadata,
    Column("ott_id", Integer, primary_key=True),
    Column("name", Text, nullable=False),
    Column("parent_ott_id", Integer),
    Column("rank", Text),
    Column("child_count", Integer),
    Column("has_metadata", Integer)
)

metadata_table = Table(
    "metadata", metadata,
    Column("ott_id", Integer, ForeignKey("nodes.ott_id"), primary_key=True),
    Column("wikidata_q", Text),
    Column("common_name", Text),
    Column("description", Text),
    Column("full_description", Text),
    Column("image_url", Text),
    Column("wiki_page_url", Text),
    Column("image_thumb", Text),
    Column("last_updated", DateTime),
    Column("enriched_score", Float)
)

def initialize_postgres_db():
    metadata.create_all(engine)
    print("Tables created.")