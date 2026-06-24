"""Audit broad data classes behind the reported GitHub issues.

This is read-only. It writes TSV reports under logs/issue_audits so repair work
can be reviewed before mutating the local database.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from sqlalchemy import text

from cladecanvas.db import Session


REPORT_DIR = Path("logs") / "issue_audits"


def write_tsv(path: Path, rows, fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    print(f"[report] {path}")


def scalar(session, sql: str) -> int:
    return int(session.execute(text(sql)).scalar() or 0)


def audit_counts(session) -> None:
    counts = {
        "duplicate_qids": scalar(
            session,
            """
            SELECT count(*) FROM (
              SELECT wikidata_q
              FROM metadata
              WHERE wikidata_q IS NOT NULL
              GROUP BY wikidata_q
              HAVING count(*) > 1
            ) q
            """,
        ),
        "duplicate_qid_rows": scalar(
            session,
            """
            SELECT count(*) FROM metadata m
            WHERE m.wikidata_q IN (
              SELECT wikidata_q
              FROM metadata
              WHERE wikidata_q IS NOT NULL
              GROUP BY wikidata_q
              HAVING count(*) > 1
            )
            """,
        ),
        "homonymous_node_names": scalar(
            session,
            """
            SELECT count(*) FROM (
              SELECT lower(name)
              FROM nodes
              WHERE ott_id IS NOT NULL
              GROUP BY lower(name)
              HAVING count(*) > 1
            ) q
            """,
        ),
        "taxonomy_only_with_children": scalar(
            session,
            """
            SELECT count(*)
            FROM nodes n
            WHERE n.ott_id IS NOT NULL
              AND n.num_tips IS NULL
              AND EXISTS (
                SELECT 1 FROM nodes c WHERE c.parent_node_id = n.node_id
              )
            """,
        ),
        "specimen_like_metadata_rows": scalar(
            session,
            """
            SELECT count(*)
            FROM nodes n
            JOIN metadata m ON m.node_id = n.node_id
            WHERE n.name ~* '(^|[[:space:]])sp\\.|BOLD|environmental|uncultured|unclassified|unidentified'
            """,
        ),
        "missing_or_legacy_provenance_rows": scalar(
            session,
            """
            SELECT count(*)
            FROM metadata
            WHERE source_match_method IS NULL
               OR field_sources::text = '{}'
            """,
        ),
    }
    print("[counts]")
    for label, count in counts.items():
        print(f"{label}\t{count}")


def report_homonyms(session, limit: int) -> None:
    rows = session.execute(
        text(
            """
            WITH homonyms AS (
              SELECT lower(name) AS lname
              FROM nodes
              WHERE ott_id IS NOT NULL
              GROUP BY lower(name)
              HAVING count(*) > 1
            )
            SELECT
              n.node_id,
              n.ott_id,
              n.name,
              n.parent_node_id,
              n.num_tips,
              n.rank,
              m.wikidata_q,
              m.common_name,
              m.description,
              m.source_match_method,
              m.provenance_confidence
            FROM nodes n
            JOIN homonyms h ON h.lname = lower(n.name)
            LEFT JOIN metadata m ON m.node_id = n.node_id
            ORDER BY lower(n.name), n.num_tips DESC NULLS LAST, n.node_id
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).mappings()
    write_tsv(
        REPORT_DIR / "homonymous_nodes.tsv",
        [dict(row) for row in rows],
        [
            "node_id",
            "ott_id",
            "name",
            "parent_node_id",
            "num_tips",
            "rank",
            "wikidata_q",
            "common_name",
            "description",
            "source_match_method",
            "provenance_confidence",
        ],
    )


def report_duplicate_qids(session, limit: int) -> None:
    rows = session.execute(
        text(
            """
            WITH dupes AS (
              SELECT wikidata_q
              FROM metadata
              WHERE wikidata_q IS NOT NULL
              GROUP BY wikidata_q
              HAVING count(*) > 1
            )
            SELECT
              m.wikidata_q,
              m.node_id,
              n.ott_id,
              n.name,
              n.parent_node_id,
              n.num_tips,
              m.common_name,
              m.description,
              m.source_match_method,
              m.provenance_confidence
            FROM metadata m
            JOIN dupes d ON d.wikidata_q = m.wikidata_q
            JOIN nodes n ON n.node_id = m.node_id
            ORDER BY m.wikidata_q, n.num_tips DESC NULLS LAST, n.node_id
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).mappings()
    write_tsv(
        REPORT_DIR / "duplicate_wikidata_qids.tsv",
        [dict(row) for row in rows],
        [
            "wikidata_q",
            "node_id",
            "ott_id",
            "name",
            "parent_node_id",
            "num_tips",
            "common_name",
            "description",
            "source_match_method",
            "provenance_confidence",
        ],
    )


def report_taxonomy_only_with_children(session, limit: int) -> None:
    rows = session.execute(
        text(
            """
            SELECT
              n.node_id,
              n.ott_id,
              n.name,
              n.parent_node_id,
              n.rank,
              count(c.node_id) AS child_count,
              m.wikidata_q,
              m.description
            FROM nodes n
            JOIN nodes c ON c.parent_node_id = n.node_id
            LEFT JOIN metadata m ON m.node_id = n.node_id
            WHERE n.ott_id IS NOT NULL
              AND n.num_tips IS NULL
            GROUP BY
              n.node_id, n.ott_id, n.name, n.parent_node_id, n.rank,
              m.wikidata_q, m.description
            ORDER BY child_count DESC, n.name
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).mappings()
    write_tsv(
        REPORT_DIR / "taxonomy_only_with_children.tsv",
        [dict(row) for row in rows],
        [
            "node_id",
            "ott_id",
            "name",
            "parent_node_id",
            "rank",
            "child_count",
            "wikidata_q",
            "description",
        ],
    )


def report_specimen_like_metadata(session, limit: int) -> None:
    rows = session.execute(
        text(
            """
            SELECT
              n.node_id,
              n.ott_id,
              n.name,
              n.parent_node_id,
              m.wikidata_q,
              m.common_name,
              m.description,
              m.source_match_method,
              m.provenance_confidence
            FROM nodes n
            JOIN metadata m ON m.node_id = n.node_id
            WHERE n.name ~* '(^|[[:space:]])sp\\.|BOLD|environmental|uncultured|unclassified|unidentified'
            ORDER BY n.name
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).mappings()
    write_tsv(
        REPORT_DIR / "specimen_like_metadata.tsv",
        [dict(row) for row in rows],
        [
            "node_id",
            "ott_id",
            "name",
            "parent_node_id",
            "wikidata_q",
            "common_name",
            "description",
            "source_match_method",
            "provenance_confidence",
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5000)
    args = parser.parse_args()

    with Session() as session:
        audit_counts(session)
        report_homonyms(session, args.limit)
        report_duplicate_qids(session, args.limit)
        report_taxonomy_only_with_children(session, args.limit)
        report_specimen_like_metadata(session, args.limit)


if __name__ == "__main__":
    main()
