import time
import random
from multiprocessing import Process
from cladecanvas.db import Session
from cladecanvas.enrich import fetch_wikidata
from cladecanvas.schema import metadata_table
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import text
import argparse

def get_batch(session, limit):
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

def enrich_batch(worker_id, batch_size, sleep_time, loop_count):
    for i in range(loop_count):
        session = Session()
        try:
            ott_ids = get_batch(session, batch_size)
            if not ott_ids:
                print(f"[Worker {worker_id}] No more taxa to enrich.")
                break

            enriched = fetch_wikidata(ott_ids)
            if enriched:
                deduped = {row['ott_id']: row for row in enriched}.values()

                metadata_columns = {c.name for c in metadata_table.columns}
                sanitized = [{k: row[k] for k in row if k in metadata_columns} for row in deduped]

                insert_stmt = pg_insert(metadata_table).values(sanitized)

                update_fields = {
                    k: insert_stmt.excluded[k]
                    for k in metadata_columns
                    if k != "ott_id"
                }

                stmt = insert_stmt.on_conflict_do_update(
                    index_elements=["ott_id"],
                    set_=update_fields
                )
                session.execute(stmt)

                # Update nodes.rank and has_metadata
                for row in deduped:
                    session.execute(
                        text("UPDATE nodes SET rank = :rank, has_metadata = 1 WHERE ott_id = :ott"),
                        {"rank": row.get("rank"), "ott": row["ott_id"]}
                    )

                session.commit()
                print(f"[Worker {worker_id}] Enriched {len(deduped)} entries.")
        except Exception as e:
            import traceback
            print(f"[Worker {worker_id}] ❌ Error: {e}")
            traceback.print_exc()
            session.rollback()
        finally:
            session.close()
        time.sleep(sleep_time + random.uniform(0, 0.5))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--loops", type=int, default=10)
    parser.add_argument("--sleep", type=float, default=1.5)
    args = parser.parse_args()

    processes = []
    for i in range(args.workers):
        p = Process(
            target=enrich_batch,
            args=(i, args.limit, args.sleep, args.loops)
        )
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

if __name__ == "__main__":
    main()