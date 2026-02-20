"""One-shot script: find and re-enrich nodes whose metadata came from
the wrong Wikidata entry (duplicate P9157 values in Wikidata)."""

import re
import time
from cladecanvas.db import Session
from cladecanvas.enrich import fetch_wikidata
from cladecanvas.schema import metadata_table
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import text

LATIN_SUFFIX = re.compile(
    r'^[A-Z][a-z]+(?:idae|inae|oidea|aceae|ales|ini|ina|ida|oida|'
    r'phora|poda|ata|oza|ia|us|is|ae|a|es|ii)$'
)

def find_wrong_entries(session):
    """Return nodes where metadata common_name is a different Latin taxon."""
    rows = session.execute(text("""
        SELECT n.node_id, n.name, n.ott_id, m.common_name, n.num_tips
        FROM nodes n
        JOIN metadata m ON m.node_id = n.node_id
        WHERE n.ott_id IS NOT NULL
          AND m.common_name IS NOT NULL
          AND LOWER(m.common_name) != LOWER(n.name)
        ORDER BY n.num_tips DESC NULLS LAST
    """)).fetchall()

    wrong = []
    for r in rows:
        node_name, common = r[1], r[3]
        # English common names are fine (lowercase or multi-word)
        if common[0].islower() or ' ' in common:
            continue
        # Same root = variant spelling, not wrong
        if node_name[:5].lower() == common[:5].lower():
            continue
        # If it looks like a Latin taxon name, it's likely the wrong Wikidata entry
        if LATIN_SUFFIX.match(common):
            wrong.append({
                'node_id': r[0], 'name': r[1], 'ott_id': r[2],
                'wrong_common': r[3], 'num_tips': r[4]
            })
    return wrong


def re_enrich_batch(session, nodes, batch_size=50):
    """Re-enrich a list of nodes using the fixed fetch_wikidata."""
    total_fixed = 0
    for i in range(0, len(nodes), batch_size):
        batch = nodes[i:i + batch_size]
        ott_nodes = [{'ott_id': n['ott_id'], 'name': n['name'], 'node_id': n['node_id']}
                     for n in batch]

        enriched = fetch_wikidata(ott_nodes)
        if not enriched:
            continue

        node_id_map = {n['ott_id']: n['node_id'] for n in batch}
        for r in enriched:
            if 'node_id' not in r:
                r['node_id'] = node_id_map.get(r['ott_id'])

        metadata_columns = {c.name for c in metadata_table.columns}
        deduped = {r['node_id']: {k: v for k, v in r.items() if k in metadata_columns}
                   for r in enriched if r.get('node_id')}.values()

        if deduped:
            insert_stmt = pg_insert(metadata_table).values(list(deduped))
            update_fields = {
                k: insert_stmt.excluded[k]
                for k in next(iter(deduped)) if k != 'node_id'
            }
            stmt = insert_stmt.on_conflict_do_update(
                index_elements=['node_id'], set_=update_fields
            )
            session.execute(stmt)
            session.commit()
            total_fixed += len(list(deduped))

        print(f"  Batch {i // batch_size + 1}: re-enriched {len(list(deduped))} nodes")
        time.sleep(1)  # respect Wikidata rate limits

    return total_fixed


if __name__ == '__main__':
    session = Session()

    wrong = find_wrong_entries(session)
    print(f"Found {len(wrong)} nodes with wrong Latin-taxon metadata")
    print(f"Top 10:")
    for n in wrong[:10]:
        print(f"  {n['node_id']:20s}  {n['name']:30s}  wrong={n['wrong_common']:30s}  tips={n['num_tips']}")

    print(f"\nRe-enriching all {len(wrong)} nodes...")
    fixed = re_enrich_batch(session, wrong)
    print(f"\nDone. Fixed {fixed} nodes.")
    session.close()
