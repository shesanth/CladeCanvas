from sqlalchemy import MetaData, Table, Column, Integer, Text, ForeignKey, DateTime, Float
from sqlalchemy import text as sa_text
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
    Column("display_name", Text, nullable=True)
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
    Column("enriched_score", Float)
)


def initialize_postgres_db():
    metadata.create_all(engine)
    with engine.connect() as conn:
        conn.execute(sa_text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_nodes_ott_id "
            "ON nodes(ott_id) WHERE ott_id IS NOT NULL"
        ))
        conn.execute(sa_text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_metadata_ott_id "
            "ON metadata(ott_id) WHERE ott_id IS NOT NULL"
        ))
        conn.commit()
    print("Tables created.")


def migrate_schema():
    """Migrate an existing DB (ott_id INTEGER PK) to the new node_id TEXT PK schema.
    Preserves all existing rows and metadata. Safe to re-run."""
    with engine.connect() as conn:
        # ── nodes ─────────────────────────────────────────────────────────────
        conn.execute(sa_text(
            "ALTER TABLE nodes ADD COLUMN IF NOT EXISTS node_id TEXT"
        ))
        conn.execute(sa_text(
            "ALTER TABLE nodes ADD COLUMN IF NOT EXISTS parent_node_id TEXT"
        ))
        conn.execute(sa_text(
            "UPDATE nodes SET node_id = 'ott' || ott_id::text "
            "WHERE node_id IS NULL AND ott_id IS NOT NULL"
        ))
        conn.execute(sa_text(
            "UPDATE nodes SET parent_node_id = 'ott' || parent_ott_id::text "
            "WHERE parent_node_id IS NULL AND parent_ott_id IS NOT NULL"
        ))
        # Drop metadata FK that references nodes PK first (so we can swap the PK)
        for row in conn.execute(sa_text("""
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_name = 'metadata' AND constraint_type = 'FOREIGN KEY'
        """)).fetchall():
            conn.execute(sa_text(f"ALTER TABLE metadata DROP CONSTRAINT {row[0]}"))

        # Drop old PK on ott_id, promote node_id
        pk = conn.execute(sa_text("""
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_name = 'nodes' AND constraint_type = 'PRIMARY KEY'
        """)).fetchone()
        if pk:
            conn.execute(sa_text(f"ALTER TABLE nodes DROP CONSTRAINT {pk[0]}"))
        conn.execute(sa_text("ALTER TABLE nodes ALTER COLUMN node_id SET NOT NULL"))
        conn.execute(sa_text("ALTER TABLE nodes ADD PRIMARY KEY (node_id)"))
        conn.execute(sa_text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_nodes_ott_id "
            "ON nodes(ott_id) WHERE ott_id IS NOT NULL"
        ))

        # ── metadata ──────────────────────────────────────────────────────────
        conn.execute(sa_text(
            "ALTER TABLE metadata ADD COLUMN IF NOT EXISTS node_id TEXT"
        ))
        conn.execute(sa_text(
            "UPDATE metadata SET node_id = 'ott' || ott_id::text "
            "WHERE node_id IS NULL AND ott_id IS NOT NULL"
        ))
        # Drop FK and old PK
        for row in conn.execute(sa_text("""
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_name = 'metadata'
            AND constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY')
        """)).fetchall():
            conn.execute(sa_text(f"ALTER TABLE metadata DROP CONSTRAINT {row[0]}"))
        conn.execute(sa_text("ALTER TABLE metadata ALTER COLUMN node_id SET NOT NULL"))
        conn.execute(sa_text("ALTER TABLE metadata ADD PRIMARY KEY (node_id)"))
        conn.execute(sa_text(
            "ALTER TABLE metadata ADD CONSTRAINT fk_metadata_nodes "
            "FOREIGN KEY (node_id) REFERENCES nodes(node_id)"
        ))
        conn.execute(sa_text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_metadata_ott_id "
            "ON metadata(ott_id) WHERE ott_id IS NOT NULL"
        ))

        conn.commit()
    print("Schema migration complete.")
