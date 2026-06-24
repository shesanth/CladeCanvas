"""Find metadata rows whose Wikidata entity points at a different OTT ID.

Run scripts/audit_issue_classes.py first. By default this script reads the TSV
reports generated there, which is much faster than regrouping millions of DB rows.
"""

from __future__ import annotations

import argparse
import csv
import re
import time
from pathlib import Path

import requests
from sqlalchemy import text

from cladecanvas.db import Session
from cladecanvas.enrich import HEADERS


REPORT_DIR = Path("logs") / "issue_audits"
REPORT_PATH = REPORT_DIR / "wikidata_ott_mismatches.tsv"
HOMONYM_REPORT = REPORT_DIR / "homonymous_nodes.tsv"
DUPLICATE_QID_REPORT = REPORT_DIR / "duplicate_wikidata_qids.tsv"


def chunks(items: list[str], size: int):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def qid_sort_key(qid: str) -> int:
    match = re.match(r"Q(\d+)$", qid)
    return int(match.group(1)) if match else 0


def fetch_qid_ott_map(qids: list[str], batch_size: int = 100) -> dict[str, set[int]]:
    qid_to_otts: dict[str, set[int]] = {qid: set() for qid in qids}
    for batch in chunks(qids, batch_size):
        values = " ".join(f"wd:{qid}" for qid in batch)
        query = f"""
SELECT ?item ?ott WHERE {{
  VALUES ?item {{ {values} }}
  ?item wdt:P9157 ?ott .
}}
"""
        response = requests.get(
            "https://query.wikidata.org/sparql",
            params={"query": query, "format": "json"},
            headers=HEADERS,
            timeout=60,
        )
        response.raise_for_status()
        bindings = response.json().get("results", {}).get("bindings", [])
        for binding in bindings:
            qid = binding["item"]["value"].rsplit("/", 1)[-1]
            try:
                qid_to_otts.setdefault(qid, set()).add(int(binding["ott"]["value"]))
            except (KeyError, ValueError):
                continue
        print(f"[wikidata] checked {min(len(qids), len(batch) + sum(1 for _ in []))} qids in current batch", flush=True)
        time.sleep(0.2)
    return qid_to_otts


def _row_from_report(row: dict) -> dict | None:
    node_id = row.get("node_id")
    wikidata_q = row.get("wikidata_q")
    ott_id = row.get("ott_id")
    if not node_id or not wikidata_q or not ott_id:
        return None
    return {
        "node_id": node_id,
        "ott_id": int(ott_id),
        "name": row.get("name"),
        "parent_node_id": row.get("parent_node_id"),
        "num_tips": int(row["num_tips"]) if row.get("num_tips") else None,
        "wikidata_q": wikidata_q,
        "common_name": row.get("common_name"),
        "description": row.get("description"),
    }


def load_candidate_rows_from_reports(limit: int | None) -> list[dict]:
    rows_by_node_id: dict[str, dict] = {}
    for path in (HOMONYM_REPORT, DUPLICATE_QID_REPORT):
        if not path.exists():
            continue
        with path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            for raw_row in reader:
                row = _row_from_report(raw_row)
                if row is None:
                    continue
                rows_by_node_id[row["node_id"]] = row
                if limit and len(rows_by_node_id) >= limit:
                    return list(rows_by_node_id.values())
    return list(rows_by_node_id.values())


def load_candidate_rows_from_db(session, limit: int | None) -> list[dict]:
    sql = """
        WITH duplicate_qids AS (
          SELECT wikidata_q
          FROM metadata
          WHERE wikidata_q IS NOT NULL
          GROUP BY wikidata_q
          HAVING count(*) > 1
        ),
        homonym_names AS (
          SELECT lower(name) AS lname
          FROM nodes
          WHERE ott_id IS NOT NULL
          GROUP BY lower(name)
          HAVING count(*) > 1
        )
        SELECT DISTINCT
          n.node_id,
          n.ott_id,
          n.name,
          n.parent_node_id,
          n.num_tips,
          m.wikidata_q,
          m.common_name,
          m.description
        FROM nodes n
        JOIN metadata m ON m.node_id = n.node_id
        WHERE n.ott_id IS NOT NULL
          AND m.wikidata_q IS NOT NULL
          AND (
            m.wikidata_q IN (SELECT wikidata_q FROM duplicate_qids)
            OR lower(n.name) IN (SELECT lname FROM homonym_names)
          )
        ORDER BY n.node_id
    """
    if limit:
        sql += "\nLIMIT :limit"
        rows = session.execute(text(sql), {"limit": limit}).mappings()
    else:
        rows = session.execute(text(sql)).mappings()
    return [dict(row) for row in rows]


def write_report(rows: list[dict]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "node_id",
        "node_ott_id",
        "node_name",
        "parent_node_id",
        "num_tips",
        "wikidata_q",
        "wikidata_p9157_ott_ids",
        "common_name",
        "description",
    ]
    with REPORT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    print(f"[report] {REPORT_PATH} ({len(rows)} rows)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--db-candidates",
        action="store_true",
        help="Load candidates directly from the DB instead of logs/issue_audits TSVs.",
    )
    args = parser.parse_args()

    if args.db_candidates:
        with Session() as session:
            candidates = load_candidate_rows_from_db(session, args.limit)
    else:
        candidates = load_candidate_rows_from_reports(args.limit)
        if not candidates:
            raise SystemExit(
                "No TSV candidates found. Run scripts/audit_issue_classes.py first "
                "or pass --db-candidates."
            )

    qids = sorted({row["wikidata_q"] for row in candidates}, key=qid_sort_key)
    print(f"[audit] {len(candidates)} candidate rows, {len(qids)} qids", flush=True)
    qid_to_otts = fetch_qid_ott_map(qids)

    mismatches = []
    for row in candidates:
        wikidata_otts = qid_to_otts.get(row["wikidata_q"], set())
        if wikidata_otts and row["ott_id"] not in wikidata_otts:
            mismatches.append({
                "node_id": row["node_id"],
                "node_ott_id": row["ott_id"],
                "node_name": row["name"],
                "parent_node_id": row["parent_node_id"],
                "num_tips": row["num_tips"],
                "wikidata_q": row["wikidata_q"],
                "wikidata_p9157_ott_ids": ",".join(str(ott) for ott in sorted(wikidata_otts)),
                "common_name": row["common_name"],
                "description": row["description"],
            })

    write_report(mismatches)


if __name__ == "__main__":
    main()
