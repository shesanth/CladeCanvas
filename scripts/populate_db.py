import argparse
from pathlib import Path
import pandas as pd
import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import text

from cladecanvas.db import Session
from cladecanvas.schema import initialize_postgres_db, nodes, metadata_table
from cladecanvas.enrich import fetch_wikidata

DATA_CSV = Path("data/metazoa_nodes.csv")
LOG_FILE = Path("logs/enrich_errors.log")
LOG_FILE.parent.mkdir(exist_ok=True)

logging.basicConfig(filename=LOG_FILE, level=logging.ERROR, format='%(asctime)s %(message)s')

def load_nodes_from_csv(session):
    df = pd.read_csv(DATA_CSV, dtype={"ott_id": "Int64", "parent_ott_id": "Int64"})
    records = df.dropna(subset=["ott_id"]).to_dict("records")
    stmt = pg_insert(nodes).values(records).on_conflict_do_nothing()
    session.execute(stmt)
    session.commit()
    print(f"Inserted {len(records)} nodes (deduplicated).")

def get_missing_ott_ids(session, limit):
    result = session.execute(text(f"""
        SELECT n.ott_id
        FROM nodes n
        WHERE NOT EXISTS (
            SELECT 1 FROM metadata m WHERE m.ott_id = n.ott_id
        )
        ORDER BY RANDOM()
        LIMIT {limit}
    """))
    return [row[0] for row in result.fetchall()]

def enrich_and_store_metadata(session, ott_ids):
    try:
        rows = session.execute(
            text("SELECT ott_id, name FROM nodes WHERE ott_id = ANY(:ids)"),
            {"ids": ott_ids}
        ).fetchall()
        enriched = fetch_wikidata([{"ott_id": row[0], "name": row[1]} for row in rows])

        # Deduplicate records by OTT ID (last one wins)
        deduped = {record["ott_id"]: record for record in enriched}.values()

        if deduped:
            insert_stmt = pg_insert(metadata_table).values(list(deduped))
            update_fields = {
                k: insert_stmt.excluded[k]
                for k in next(iter(deduped)) if k != "ott_id"
            }
            stmt = insert_stmt.on_conflict_do_update(
                index_elements=["ott_id"],
                set_=update_fields
            )
            session.execute(stmt)
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
    parser.add_argument("--max-batches", type=int, default=None, help="Stop after this many batches")

    args = parser.parse_args()

    initialize_postgres_db()
    session = Session()

    if not args.skip_load:
        print("Loading nodes from CSV…")
        load_nodes_from_csv(session)

    batch_count = 0
    while True:
        ott_ids = get_missing_ott_ids(session, args.limit)
        if not ott_ids:
            print("All taxa are enriched.")
            break

        print(f"Enriching batch of {len(ott_ids)} OTTs: {ott_ids}")
        enrich_and_store_metadata(session, ott_ids)

        batch_count += 1
        if args.max_batches and batch_count >= args.max_batches:
            print(f"Stopping after {batch_count} batches.")
            break

    session.close()

if __name__ == "__main__":
    main()
