"""Backfill missing metadata without blocking on repeated no-match taxa.

The original enrichment loop only checks whether a metadata row exists. If a
high-priority taxon has no Wikidata match, it stays missing and can be selected
again forever. This runner records every attempt, so the queue drains toward
actual completion: success rows get metadata, misses get durable no_match state,
and transient errors can be retried later.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from cladecanvas.db import Session, assert_writes_allowed
from cladecanvas.enrich import fetch_wikidata
from cladecanvas.schema import metadata_enrichment_attempts, metadata_table


DEFAULT_RETRY_DAYS = 30


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write metadata and attempt rows.")
    parser.add_argument("--limit", type=int, default=100, help="Batch size per enrichment call.")
    parser.add_argument("--max-batches", type=int, default=1, help="Stop after this many batches.")
    parser.add_argument("--ott-id", action="append", type=int, default=[], help="Target a specific OTT ID. Repeatable.")
    parser.add_argument("--node-id", action="append", default=[], help="Target a specific node_id. Repeatable.")
    parser.add_argument("--rank", action="append", default=[], help="Restrict queue to rank. Repeatable.")
    parser.add_argument("--leaf-only", action="store_true", help="Only enrich leaf taxa with num_tips = 0.")
    parser.add_argument("--name-like", help="Restrict queue to names matching an ILIKE pattern, e.g. 'Glaucidium%%'.")
    parser.add_argument(
        "--refresh-existing",
        action="store_true",
        help="Re-enrich matching rows even when metadata already exists. Best used with explicit targets.",
    )
    parser.add_argument(
        "--include-attempted",
        action="store_true",
        help="Ignore previous attempt state and retry matching missing rows.",
    )
    parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="Retry rows marked error when next_retry_at is due.",
    )
    parser.add_argument(
        "--retry-no-match-after-days",
        type=int,
        default=None,
        help="Retry no_match rows older than this many days.",
    )
    parser.add_argument(
        "--order",
        choices=("coverage", "largest", "random"),
        default="coverage",
        help="Queue ordering. coverage prioritizes ranked species and leaf taxa.",
    )
    return parser.parse_args()


def load_batch(session, args: argparse.Namespace) -> list[dict]:
    params: dict = {"limit": args.limit}
    where = ["n.ott_id IS NOT NULL"]
    if not args.refresh_existing:
        where.append("m.node_id IS NULL")

    if args.ott_id:
        where.append("n.ott_id = ANY(:ott_ids)")
        params["ott_ids"] = args.ott_id
    if args.node_id:
        where.append("n.node_id = ANY(:node_ids)")
        params["node_ids"] = args.node_id
    if args.rank:
        where.append("n.rank = ANY(:ranks)")
        params["ranks"] = args.rank
    if args.leaf_only:
        where.append("n.num_tips = 0")
    if args.name_like:
        where.append("n.name ILIKE :name_like")
        params["name_like"] = args.name_like

    targeted = bool(args.ott_id or args.node_id)
    if not targeted and not args.include_attempted:
        retry_clauses = ["a.node_id IS NULL"]
        if args.retry_errors:
            retry_clauses.append("(a.status = 'error' AND (a.next_retry_at IS NULL OR a.next_retry_at <= now()))")
        if args.retry_no_match_after_days is not None:
            params["no_match_cutoff"] = datetime.now(timezone.utc) - timedelta(days=args.retry_no_match_after_days)
            retry_clauses.append("(a.status = 'no_match' AND a.last_attempted_at <= :no_match_cutoff)")
        where.append("(" + " OR ".join(retry_clauses) + ")")

    if args.order == "random":
        order_by = "ORDER BY random()"
    elif args.order == "largest":
        order_by = "ORDER BY n.num_tips DESC NULLS LAST, n.name, n.node_id"
    else:
        order_by = """
        ORDER BY
          CASE
            WHEN n.rank = 'species' THEN 0
            WHEN n.num_tips = 0 THEN 1
            WHEN n.num_tips IS NULL THEN 2
            ELSE 3
          END,
          n.num_tips DESC NULLS LAST,
          n.name,
          n.node_id
        """

    sql = f"""
        SELECT n.node_id, n.ott_id, n.name
        FROM nodes n
        LEFT JOIN metadata m ON m.node_id = n.node_id
        LEFT JOIN metadata_enrichment_attempts a ON a.node_id = n.node_id
        WHERE {' AND '.join(where)}
        {order_by}
        LIMIT :limit
    """
    rows = session.execute(text(sql), params).mappings().fetchall()
    return [dict(row) for row in rows]


def store_enrichment(session, batch: list[dict], enriched: list[dict], apply: bool) -> tuple[int, int]:
    now = datetime.now(timezone.utc)
    node_id_by_ott = {row["ott_id"]: row["node_id"] for row in batch}
    batch_by_node_id = {row["node_id"]: row for row in batch}

    for row in enriched:
        if not row.get("node_id"):
            row["node_id"] = node_id_by_ott.get(row.get("ott_id"))

    metadata_columns = {column.name for column in metadata_table.columns}
    deduped = {
        row["node_id"]: {key: value for key, value in row.items() if key in metadata_columns}
        for row in enriched
        if row.get("node_id")
    }

    success_ids = set(deduped)
    if apply and deduped:
        records = list(deduped.values())
        insert_stmt = pg_insert(metadata_table).values(records)
        update_fields = {
            key: insert_stmt.excluded[key]
            for key in records[0]
            if key != "node_id"
        }
        session.execute(
            insert_stmt.on_conflict_do_update(
                index_elements=["node_id"],
                set_=update_fields,
            )
        )
        for row in enriched:
            node_id = row.get("node_id")
            if node_id in success_ids:
                session.execute(
                    text(
                        "UPDATE nodes SET rank = COALESCE(:rank, rank), has_metadata = 1 "
                        "WHERE node_id = :node_id"
                    ),
                    {"node_id": node_id, "rank": row.get("rank")},
                )

    attempt_records = []
    enriched_by_node_id = {row.get("node_id"): row for row in enriched if row.get("node_id")}
    for node_id, original in batch_by_node_id.items():
        result = enriched_by_node_id.get(node_id)
        status = "success" if node_id in success_ids else "no_match"
        attempt_records.append({
            "node_id": node_id,
            "ott_id": original["ott_id"],
            "name": original["name"],
            "status": status,
            "attempt_count": 1,
            "last_attempted_at": now,
            "last_success_at": now if status == "success" else None,
            "last_provider": result.get("source_label") if result else "Wikidata",
            "last_match_method": result.get("source_match_method") if result else None,
            "last_error": None,
            "created_at": now,
            "updated_at": now,
            "next_retry_at": None if status == "success" else now + timedelta(days=DEFAULT_RETRY_DAYS),
        })

    if apply and attempt_records:
        upsert_attempts(session, attempt_records)

    return len(success_ids), len(batch) - len(success_ids)


def record_error_attempts(session, batch: Iterable[dict], error: Exception, apply: bool) -> None:
    now = datetime.now(timezone.utc)
    message = str(error)[:1000]
    records = [
        {
            "node_id": row["node_id"],
            "ott_id": row["ott_id"],
            "name": row["name"],
            "status": "error",
            "attempt_count": 1,
            "last_attempted_at": now,
            "last_success_at": None,
            "last_provider": "Wikidata",
            "last_match_method": None,
            "last_error": message,
            "created_at": now,
            "updated_at": now,
            "next_retry_at": now + timedelta(days=1),
        }
        for row in batch
    ]
    if apply and records:
        upsert_attempts(session, records)


def upsert_attempts(session, records: list[dict]) -> None:
    insert_stmt = pg_insert(metadata_enrichment_attempts).values(records)
    session.execute(
        insert_stmt.on_conflict_do_update(
            index_elements=["node_id"],
            set_={
                "ott_id": insert_stmt.excluded.ott_id,
                "name": insert_stmt.excluded.name,
                "status": insert_stmt.excluded.status,
                "attempt_count": metadata_enrichment_attempts.c.attempt_count + 1,
                "last_attempted_at": insert_stmt.excluded.last_attempted_at,
                "last_success_at": insert_stmt.excluded.last_success_at,
                "last_provider": insert_stmt.excluded.last_provider,
                "last_match_method": insert_stmt.excluded.last_match_method,
                "last_error": insert_stmt.excluded.last_error,
                "updated_at": insert_stmt.excluded.updated_at,
                "next_retry_at": insert_stmt.excluded.next_retry_at,
            },
        )
    )


def main() -> None:
    args = parse_args()
    if args.apply:
        assert_writes_allowed("metadata backfill")
    else:
        print("[dry-run] no database writes will be made; pass --apply to write")

    total_success = 0
    total_no_match = 0
    total_errors = 0

    with Session() as session:
        for batch_index in range(args.max_batches):
            batch = load_batch(session, args)
            if not batch:
                print("[done] no matching missing metadata rows remain")
                break

            print(
                f"[batch {batch_index + 1}] attempting {len(batch)} taxa; "
                f"first={batch[0]['node_id']} {batch[0]['name']}"
            )
            try:
                enriched = fetch_wikidata(batch)
                successes, no_matches = store_enrichment(session, batch, enriched, args.apply)
                if args.apply:
                    session.commit()
                total_success += successes
                total_no_match += no_matches
                print(f"[batch {batch_index + 1}] success={successes} no_match={no_matches}")
            except Exception as exc:  # noqa: BLE001 - mark batch retryable and continue/exit cleanly
                session.rollback()
                record_error_attempts(session, batch, exc, args.apply)
                if args.apply:
                    session.commit()
                total_errors += len(batch)
                print(f"[batch {batch_index + 1}] error={exc}")

    print(f"[summary] success={total_success} no_match={total_no_match} errors={total_errors}")


if __name__ == "__main__":
    main()
