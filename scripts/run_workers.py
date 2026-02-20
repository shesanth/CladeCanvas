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
        SELECT n.ott_id, n.name, n.node_id
        FROM nodes n
        WHERE n.ott_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM metadata m WHERE m.node_id = n.node_id
          )
        ORDER BY RANDOM()
        LIMIT {limit}
    """))
    return [{'ott_id': row[0], 'name': row[1], 'node_id': row[2]} for row in result.fetchall()]

def enrich_batch(worker_id, batch_size, sleep_time, loop_count):
    for i in range(loop_count):
        session = Session()
        try:
            print(f"[Worker {worker_id}] Requesting batch of {batch_size}…")
            batch = get_batch(session, batch_size)
            if not batch:
                print(f"[Worker {worker_id}] No more taxa to enrich.")
                break

            enriched = fetch_wikidata(batch)
            if enriched:
                # Attach node_id from the batch lookup
                node_id_map = {b['ott_id']: b['node_id'] for b in batch}
                for row in enriched:
                    if 'node_id' not in row:
                        row['node_id'] = node_id_map.get(row['ott_id'])

                metadata_columns = {c.name for c in metadata_table.columns}
                deduped = {row['node_id']: {k: v for k, v in row.items() if k in metadata_columns}
                           for row in enriched if row.get('node_id')}.values()

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

                for row in enriched:
                    nid = row.get('node_id') or node_id_map.get(row.get('ott_id'))
                    if nid:
                        session.execute(
                            text("UPDATE nodes SET rank = :rank, has_metadata = 1 WHERE node_id = :nid"),
                            {"rank": row.get("rank"), "nid": nid}
                        )

                session.commit()
                print(f"[Worker {worker_id}] Enriched {len(list(deduped))} entries.")
        except Exception as e:
            import traceback
            print(f"[Worker {worker_id}] Error: {e}")
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
