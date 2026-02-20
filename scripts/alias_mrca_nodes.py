"""Find taxonomy names that map to MRCA nodes in the synthesis tree.

For each taxonomy-only node (num_tips IS NULL) at a major rank that has
metadata, query the OToL node_info API to find which synthesis tree node
it maps to. If the synthesis node is an MRCA node, store the taxon name
as display_name on that MRCA node.
"""

import time
import requests
from cladecanvas.db import Session
from sqlalchemy import text

OTOL_API = "https://api.opentreeoflife.org/v3/tree_of_life/node_info"
# Start with higher-rank taxa (most visible in tree navigation)
RANKS = ("phylum", "subphylum", "superclass", "class", "subclass",
         "superorder", "order")


def find_aliases():
    rank_list = ", ".join(f"'{r}'" for r in RANKS)
    with Session() as s:
        rows = s.execute(text(f"""
            SELECT n.name, n.ott_id, n.rank FROM nodes n
            JOIN metadata m ON m.node_id = n.node_id
            WHERE n.num_tips IS NULL AND n.ott_id IS NOT NULL
            AND n.name NOT LIKE :pat1 AND n.name NOT LIKE :pat2
            AND n.rank IN ({rank_list})
            ORDER BY n.rank, n.name
        """), dict(pat1="% sp. %", pat2="%BOLD%")).fetchall()

    print(f"Querying OToL for {len(rows)} taxonomy-only nodes...", flush=True)
    aliases = []  # (mrca_node_id, taxon_name, taxon_rank)
    errors = 0

    for i, (name, ott_id, rank) in enumerate(rows):
        try:
            resp = requests.post(OTOL_API, json={"ott_id": ott_id}, timeout=30)
            d = resp.json()
            synth_node_id = d.get("node_id", "")
            if synth_node_id.startswith("mrcaott"):
                aliases.append((synth_node_id, name, rank))
                print(f"  [{i+1}/{len(rows)}] {name} ({rank}) -> {synth_node_id}",
                      flush=True)
        except Exception as e:
            errors += 1
            print(f"  [{i+1}/{len(rows)}] {name} ERROR: {e}", flush=True)

        if (i + 1) % 50 == 0:
            print(f"  ... progress: {i+1}/{len(rows)}, "
                  f"{len(aliases)} aliases found so far", flush=True)
        time.sleep(0.3)

    print(f"\nFound {len(aliases)} aliases ({errors} errors). Writing to DB...",
          flush=True)

    with Session() as s:
        for mrca_id, taxon_name, taxon_rank in aliases:
            s.execute(text("""
                UPDATE nodes SET display_name = :name
                WHERE node_id = :nid AND display_name IS NULL
            """), dict(name=taxon_name, nid=mrca_id))
        s.commit()

    print("Done.", flush=True)


if __name__ == "__main__":
    find_aliases()
