"""Repair known production data issues before the next database upload.

The script is intentionally narrow: it fixes the reported Theria/Xenarthra
metadata collisions and can canonicalize a known taxonomy-only Arachnida alias
onto the synthesis MRCA node. It defaults to dry-run mode; pass --apply to write.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from urllib.parse import quote

import requests
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from cladecanvas.db import Session, assert_writes_allowed
from cladecanvas.enrich import HEADERS, build_field_sources, fetch_wikipedia_extract
from cladecanvas.schema import metadata_table


METADATA_OVERRIDES = {
    "ott229558": {
        "qid": "Q130942",
        "rank": "subclass",
        "reason": "Theria mammal clade was enriched with moth genus metadata.",
    },
    "ott847764": {
        "qid": "Q173612",
        "rank": "superorder",
        "reason": "Xenarthra mammal clade was enriched with leaf beetle genus metadata.",
    },
}

CANONICAL_ALIASES = {
    "ott511967": {
        "canonical_node_id": "mrcaott343ott948",
        "label": "Arachnida",
        "reason": "Taxonomy-only Arachnida node duplicates the synthesis MRCA clade.",
    },
}


def fetch_entity_payload(qid: str, rank: str | None) -> dict:
    response = requests.get(
        "https://www.wikidata.org/w/api.php",
        params={
            "action": "wbgetentities",
            "ids": qid,
            "format": "json",
            "props": "labels|descriptions|claims",
            "languages": "en",
        },
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    entity = response.json()["entities"][qid]
    label = entity.get("labels", {}).get("en", {}).get("value")
    description = entity.get("descriptions", {}).get("en", {}).get("value")
    image_url = _commons_image_url(entity)
    full_description, wiki_page_url = fetch_wikipedia_extract(qid)
    source_url = f"https://www.wikidata.org/wiki/{qid}"

    return {
        "wikidata_q": qid,
        "common_name": label,
        "description": description,
        "full_description": full_description,
        "image_url": image_url,
        "image_thumb": image_url,
        "wiki_page_url": wiki_page_url,
        "rank": rank,
        "source_label": "Wikidata manual override",
        "source_url": source_url,
        "source_match_method": "manual_qid_override",
        "provenance_confidence": 1.0,
        "field_sources": build_field_sources(
            "Wikidata manual override",
            source_url,
            wiki_page_url,
        ),
    }


def _commons_image_url(entity: dict) -> str | None:
    claims = entity.get("claims", {})
    image_claims = claims.get("P18") or []
    if not image_claims:
        return None
    value = (
        image_claims[0]
        .get("mainsnak", {})
        .get("datavalue", {})
        .get("value")
    )
    if not value:
        return None
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(value)}"


def repair_metadata(session, apply: bool) -> None:
    now = datetime.now(timezone.utc)
    metadata_columns = {column.name for column in metadata_table.columns}

    for node_id, override in METADATA_OVERRIDES.items():
        node = session.execute(
            text("SELECT node_id, ott_id, name FROM nodes WHERE node_id = :node_id"),
            {"node_id": node_id},
        ).mappings().first()
        if not node:
            print(f"[metadata] missing node {node_id}; skipping")
            continue

        payload = fetch_entity_payload(override["qid"], override.get("rank"))
        record = {
            **payload,
            "node_id": node_id,
            "ott_id": node["ott_id"],
            "last_updated": now,
            "enriched_at": now,
            "enriched_score": 1.0 if (payload["description"] or payload["full_description"] or payload["image_url"]) else 0.0,
        }
        record = {key: value for key, value in record.items() if key in metadata_columns}

        print(
            f"[metadata] {node_id} {node['name']}: "
            f"{override['reason']} -> {payload['wikidata_q']} {payload['description']!r}"
        )
        if not apply:
            continue

        insert_stmt = pg_insert(metadata_table).values(record)
        update_fields = {
            key: insert_stmt.excluded[key]
            for key in record
            if key != "node_id"
        }
        session.execute(
            insert_stmt.on_conflict_do_update(
                index_elements=["node_id"],
                set_=update_fields,
            )
        )
        session.execute(
            text(
                "UPDATE nodes SET rank = :rank, has_metadata = 1 "
                "WHERE node_id = :node_id"
            ),
            {"node_id": node_id, "rank": payload["rank"]},
        )


def canonicalize_aliases(session, apply: bool) -> None:
    for alias_node_id, spec in CANONICAL_ALIASES.items():
        canonical_node_id = spec["canonical_node_id"]
        child_count = session.execute(
            text("SELECT count(*) FROM nodes WHERE parent_node_id = :alias_node_id"),
            {"alias_node_id": alias_node_id},
        ).scalar_one()
        alias_parent = session.execute(
            text("SELECT parent_node_id FROM nodes WHERE node_id = :alias_node_id"),
            {"alias_node_id": alias_node_id},
        ).scalar_one_or_none()
        canonical_parent = session.execute(
            text("SELECT parent_node_id FROM nodes WHERE node_id = :canonical_node_id"),
            {"canonical_node_id": canonical_node_id},
        ).scalar_one_or_none()

        if canonical_parent is None:
            print(f"[alias] missing canonical node {canonical_node_id}; skipping")
            continue

        print(
            f"[alias] {alias_node_id} -> {canonical_node_id} ({spec['label']}): "
            f"move {child_count} child rows; alias parent {alias_parent!r} -> {canonical_node_id!r}"
        )
        if not apply:
            continue

        session.execute(
            text(
                "UPDATE nodes SET parent_node_id = :canonical_node_id "
                "WHERE parent_node_id = :alias_node_id"
            ),
            {
                "canonical_node_id": canonical_node_id,
                "alias_node_id": alias_node_id,
            },
        )
        session.execute(
            text(
                "UPDATE nodes SET parent_node_id = :canonical_node_id "
                "WHERE node_id = :alias_node_id"
            ),
            {
                "canonical_node_id": canonical_node_id,
                "alias_node_id": alias_node_id,
            },
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write repairs to the configured Postgres DB.")
    parser.add_argument(
        "--skip-aliases",
        action="store_true",
        help="Only repair metadata; leave canonical alias/reparenting changes untouched.",
    )
    args = parser.parse_args()

    if args.apply:
        assert_writes_allowed("reported issue data repair")
    else:
        print("[dry-run] no database writes will be made; pass --apply to write")

    with Session() as session:
        repair_metadata(session, apply=args.apply)
        if not args.skip_aliases:
            canonicalize_aliases(session, apply=args.apply)
        if args.apply:
            session.commit()
            print("[done] repairs committed")


if __name__ == "__main__":
    main()
