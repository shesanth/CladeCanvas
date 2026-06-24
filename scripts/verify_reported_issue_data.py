"""Verify local DB repairs for the reported GitHub issue cases."""

from __future__ import annotations

import sys

from sqlalchemy import text

from cladecanvas.db import Session


EXPECTED_METADATA = {
    "ott229558": {
        "qid": "Q130942",
        "required": ("mammal",),
        "forbidden": ("insect", "moth"),
    },
    "ott847764": {
        "qid": "Q173612",
        "required": ("mammal",),
        "forbidden": ("beetle", "insect"),
    },
}

EXPECTED_ALIASES = {
    "ott511967": "mrcaott343ott948",
}


def check_metadata(session) -> list[str]:
    failures = []
    for node_id, expected in EXPECTED_METADATA.items():
        row = session.execute(
            text(
                "SELECT wikidata_q, description, full_description, source_match_method "
                "FROM metadata WHERE node_id = :node_id"
            ),
            {"node_id": node_id},
        ).mappings().first()
        if not row:
            failures.append(f"{node_id}: metadata row missing")
            continue

        combined = " ".join(
            str(row.get(field) or "").lower()
            for field in ("description", "full_description")
        )
        if row["wikidata_q"] != expected["qid"]:
            failures.append(f"{node_id}: expected {expected['qid']}, got {row['wikidata_q']}")
        for word in expected["required"]:
            if word not in combined:
                failures.append(f"{node_id}: expected text containing {word!r}")
        for word in expected["forbidden"]:
            if word in combined:
                failures.append(f"{node_id}: forbidden text still contains {word!r}")
        if row["source_match_method"] != "manual_qid_override":
            failures.append(f"{node_id}: source_match_method is {row['source_match_method']!r}")
    return failures


def check_aliases(session) -> list[str]:
    failures = []
    for alias_node_id, canonical_node_id in EXPECTED_ALIASES.items():
        parent = session.execute(
            text("SELECT parent_node_id FROM nodes WHERE node_id = :node_id"),
            {"node_id": alias_node_id},
        ).scalar_one_or_none()
        child_count = session.execute(
            text("SELECT count(*) FROM nodes WHERE parent_node_id = :node_id"),
            {"node_id": alias_node_id},
        ).scalar_one()
        canonical_child_count = session.execute(
            text("SELECT count(*) FROM nodes WHERE parent_node_id = :node_id"),
            {"node_id": canonical_node_id},
        ).scalar_one()

        if parent != canonical_node_id:
            failures.append(
                f"{alias_node_id}: expected parent {canonical_node_id}, got {parent}"
            )
        if child_count != 0:
            failures.append(f"{alias_node_id}: still has {child_count} direct children")
        if canonical_child_count == 0:
            failures.append(f"{canonical_node_id}: has no direct children after alias repair")
    return failures


def main() -> int:
    with Session() as session:
        failures = check_metadata(session) + check_aliases(session)

    if failures:
        print("[failed] reported issue repair verification failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("[ok] reported issue repair verification passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
