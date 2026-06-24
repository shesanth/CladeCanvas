"""Populate node_aliases for taxonomy-only nodes that map to MRCA nodes.

Uses OpenTree node_info as the authority. Defaults to dry-run; pass --apply to
write aliases. The script is resumable because existing aliases are skipped.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from cladecanvas.db import Session, assert_writes_allowed
from cladecanvas.enrich import HEADERS
from cladecanvas.schema import node_aliases

OTOL_NODE_INFO = "https://api.opentreeoflife.org/v3/tree_of_life/node_info"


def load_candidates(session, min_children: int, limit: int | None) -> list[dict]:
    sql = """
        SELECT n.node_id, n.ott_id, n.name, count(c.node_id) AS child_count
        FROM nodes n
        JOIN nodes c ON c.parent_node_id = n.node_id
        LEFT JOIN node_aliases a ON a.alias_node_id = n.node_id
        WHERE n.ott_id IS NOT NULL
          AND n.num_tips IS NULL
          AND a.alias_node_id IS NULL
        GROUP BY n.node_id, n.ott_id, n.name
        HAVING count(c.node_id) >= :min_children
        ORDER BY count(c.node_id) DESC, n.name, n.node_id
    """
    params = {"min_children": min_children}
    if limit:
        sql += " LIMIT :limit"
        params["limit"] = limit
    return [dict(row) for row in session.execute(text(sql), params).mappings()]


def existing_node_ids(session, node_ids: list[str]) -> set[str]:
    if not node_ids:
        return set()
    rows = session.execute(
        text("SELECT node_id FROM nodes WHERE node_id = ANY(:node_ids)"),
        {"node_ids": node_ids},
    ).fetchall()
    return {row[0] for row in rows}


def fetch_mapping(candidate: dict) -> dict:
    try:
        response = requests.post(
            OTOL_NODE_INFO,
            json={"ott_id": int(candidate["ott_id"])},
            headers=HEADERS,
            timeout=30,
        )
        if not response.ok:
            return {**candidate, "canonical_node_id": None, "error": f"http-{response.status_code}"}
        canonical_node_id = response.json().get("node_id")
        return {**candidate, "canonical_node_id": canonical_node_id, "error": None}
    except Exception as exc:  # noqa: BLE001 - report and continue batch repair
        return {**candidate, "canonical_node_id": None, "error": str(exc)}


def write_aliases(session, mappings: list[dict], apply: bool) -> int:
    canonical_ids = [row["canonical_node_id"] for row in mappings if row.get("canonical_node_id")]
    present = existing_node_ids(session, canonical_ids)
    now = datetime.now(timezone.utc)
    records = []
    for row in mappings:
        canonical = row.get("canonical_node_id")
        if not canonical or not canonical.startswith("mrcaott"):
            continue
        if canonical == row["node_id"] or canonical not in present:
            continue
        records.append({
            "alias_node_id": row["node_id"],
            "canonical_node_id": canonical,
            "reason": "opentree_node_info_mrca",
            "confidence": 1.0,
            "created_at": now,
        })

    if not records:
        return 0
    if not apply:
        for record in records[:20]:
            print(f"[dry-run] {record['alias_node_id']} -> {record['canonical_node_id']}", flush=True)
        if len(records) > 20:
            print(f"[dry-run] ... and {len(records) - 20} more", flush=True)
        return len(records)

    insert_stmt = pg_insert(node_aliases).values(records)
    session.execute(
        insert_stmt.on_conflict_do_update(
            index_elements=["alias_node_id"],
            set_={
                "canonical_node_id": insert_stmt.excluded.canonical_node_id,
                "reason": insert_stmt.excluded.reason,
                "confidence": insert_stmt.excluded.confidence,
                "created_at": insert_stmt.excluded.created_at,
            },
        )
    )
    session.commit()
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--min-children", type=int, default=2)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--chunk-size", type=int, default=500)
    args = parser.parse_args()

    if args.apply:
        assert_writes_allowed("node alias population")
    else:
        print("[dry-run] pass --apply to write aliases", flush=True)

    with Session() as session:
        candidates = load_candidates(session, args.min_children, args.limit)
    print(f"[candidates] {len(candidates)} taxonomy-only nodes", flush=True)

    total_aliases = 0
    total_checked = 0
    for start in range(0, len(candidates), args.chunk_size):
        chunk = candidates[start:start + args.chunk_size]
        mappings = []
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [executor.submit(fetch_mapping, candidate) for candidate in chunk]
            for future in as_completed(futures):
                mappings.append(future.result())
        total_checked += len(chunk)
        with Session() as session:
            written = write_aliases(session, mappings, args.apply)
        total_aliases += written
        errors = sum(1 for row in mappings if row.get("error"))
        print(
            f"[chunk] checked={total_checked}/{len(candidates)} "
            f"aliases={total_aliases} errors={errors}",
            flush=True,
        )

    print(f"[done] checked={total_checked} aliases={total_aliases}", flush=True)


if __name__ == "__main__":
    main()
