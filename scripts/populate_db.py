import argparse
from pathlib import Path
import pandas as pd
import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import text

from cladecanvas.db import Session
from cladecanvas.schema import initialize_postgres_db, migrate_schema, nodes, metadata_table
from cladecanvas.enrich import fetch_wikidata

DATA_CSV = Path("data/metazoa_nodes_synth.csv")
LOG_FILE = Path("logs/enrich_errors.log")
LOG_FILE.parent.mkdir(exist_ok=True)

logging.basicConfig(filename=LOG_FILE, level=logging.ERROR, format='%(asctime)s %(message)s')


def load_nodes_from_csv(session, batch_size=10000):
    df = pd.read_csv(DATA_CSV, dtype={"ott_id": "Int64", "num_tips": "Int64"})
    # Convert pd.NA to None so SQLAlchemy handles nullable int correctly
    records = df.where(pd.notna(df), other=None).to_dict("records")
    n_synth = sum(1 for r in records if r.get("ott_id") is None)
    total_inserted = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        excluded = pg_insert(nodes).excluded
        stmt = pg_insert(nodes).values(batch).on_conflict_do_update(
            index_elements=["node_id"],
            set_={
                "parent_node_id": excluded.parent_node_id,
                "name": excluded.name,
                "num_tips": excluded.num_tips,
            }
        )
        session.execute(stmt)
        session.commit()
        total_inserted += len(batch)
        if total_inserted % 100000 < batch_size:
            print(f"  ...{total_inserted:,}/{len(records):,} rows")
    print(f"Upserted {len(records):,} nodes ({n_synth:,} synthetic, {len(records)-n_synth:,} taxon).")


def get_missing_ott_ids(session, limit):
    # Only enrich nodes that have a real OTT ID (synthetic nodes have no Wikidata entry)
    result = session.execute(text(f"""
        SELECT n.ott_id
        FROM nodes n
        WHERE n.ott_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM metadata m WHERE m.node_id = n.node_id
          )
        ORDER BY n.num_tips DESC NULLS LAST
        LIMIT {limit}
    """))
    return [row[0] for row in result.fetchall()]


def get_priority_ott_ids(session, min_tips=1000):
    """Return all un-enriched OTT IDs with num_tips >= min_tips, most important first."""
    result = session.execute(text("""
        SELECT n.ott_id
        FROM nodes n
        WHERE n.ott_id IS NOT NULL
          AND n.num_tips >= :min_tips
          AND NOT EXISTS (
            SELECT 1 FROM metadata m WHERE m.node_id = n.node_id
          )
        ORDER BY n.num_tips DESC
    """), {"min_tips": min_tips})
    return [row[0] for row in result.fetchall()]


def enrich_and_store_metadata(session, ott_ids):
    try:
        rows = session.execute(
            text("SELECT node_id, ott_id, name FROM nodes WHERE ott_id = ANY(:ids)"),
            {"ids": ott_ids}
        ).fetchall()
        enriched = fetch_wikidata([{"ott_id": row[1], "name": row[2], "node_id": row[0]} for row in rows])

        # Attach node_id to each enriched record
        node_id_map = {row[1]: row[0] for row in rows}  # ott_id -> node_id
        for record in enriched:
            if "node_id" not in record:
                record["node_id"] = node_id_map.get(record["ott_id"])

        # Deduplicate by node_id (last one wins)
        metadata_columns = {c.name for c in metadata_table.columns}
        deduped = {r["node_id"]: {k: v for k, v in r.items() if k in metadata_columns}
                   for r in enriched if r.get("node_id")}.values()

        if deduped:
            insert_stmt = pg_insert(metadata_table).values(list(deduped))
            update_fields = {
                k: insert_stmt.excluded[k]
                for k in next(iter(deduped)) if k != "node_id"
            }
            stmt = insert_stmt.on_conflict_do_update(
                index_elements=["node_id"],
                set_=update_fields
            )
            session.execute(stmt)

            # Update rank and has_metadata on nodes table
            for record in enriched:
                nid = record.get("node_id") or node_id_map.get(record.get("ott_id"))
                if nid:
                    session.execute(
                        text("UPDATE nodes SET rank = :rank, has_metadata = 1 WHERE node_id = :nid"),
                        {"rank": record.get("rank"), "nid": nid}
                    )

            session.commit()
            print(f"Enriched and stored metadata for {len(deduped)} taxa.")
    except Exception as e:
        session.rollback()
        logging.error(f"Failed enrichment for {ott_ids}: {e}")
        print(f"Error enriching batch: {e}")


def main():
    parser = argparse.ArgumentParser(description="Populate DB with OpenTree + Wikidata metadata.")
    parser.add_argument("--limit", type=int, default=100, help="Batch size for enrichment")
    parser.add_argument("--skip-load", action="store_true", help="Skip loading nodes from CSV")
    parser.add_argument("--skip-enrich", action="store_true", help="Skip metadata enrichment")
    parser.add_argument("--max-batches", type=int, default=None, help="Stop after this many batches")
    parser.add_argument("--migrate", action="store_true",
                        help="Run schema migration (ott_id PK → node_id PK) before loading")
    parser.add_argument("--priority", action="store_true",
                        help="Enrich high-importance taxa first (by num_tips)")
    parser.add_argument("--min-tips", type=int, default=1000,
                        help="Minimum num_tips for --priority enrichment (default: 1000)")
    args = parser.parse_args()

    if args.migrate:
        print("Running schema migration…")
        migrate_schema()

    initialize_postgres_db()
    session = Session()

    if not args.skip_load:
        print("Loading nodes from CSV…")
        load_nodes_from_csv(session)

    if args.priority:
        priority_ids = get_priority_ott_ids(session, args.min_tips)
        if priority_ids:
            print(f"Priority enrichment: {len(priority_ids)} taxa with num_tips >= {args.min_tips}")
            for i in range(0, len(priority_ids), args.limit):
                batch = priority_ids[i:i + args.limit]
                print(f"  Priority batch {i//args.limit + 1}: {len(batch)} OTTs")
                enrich_and_store_metadata(session, batch)
        else:
            print("No priority taxa to enrich.")

    if args.skip_enrich:
        session.close()
        return

    batch_count = 0
    while True:
        ott_ids = get_missing_ott_ids(session, args.limit)
        if not ott_ids:
            print("All taxa are enriched.")
            break

        print(f"Enriching batch of {len(ott_ids)} OTTs: {ott_ids[:5]}{'…' if len(ott_ids)>5 else ''}")
        enrich_and_store_metadata(session, ott_ids)

        batch_count += 1
        if args.max_batches and batch_count >= args.max_batches:
            print(f"Stopping after {batch_count} batches.")
            break

    session.close()


if __name__ == "__main__":
    main()
