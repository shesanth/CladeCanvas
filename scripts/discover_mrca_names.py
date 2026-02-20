"""Programmatic discovery of clade names for synthetic MRCA nodes.

Phase 1: Wikidata reverse lookup — bulk-fetch all OTT IDs from Wikidata (P9157),
         find taxonomy-only nodes in our DB, query OToL node_info to check if
         their synthesis placement is an MRCA node.

Phase 2: Expanded OToL rank query — like alias_mrca_nodes.py but with ALL ranks
         and no metadata requirement.

Phase 3: Child-pair Wikidata search — for top unaliased MRCA nodes by num_tips,
         search Wikidata for clade articles covering both child taxa.
"""

import argparse
import time
import requests
from cladecanvas.db import Session
from sqlalchemy import text

OTOL_API = "https://api.opentreeoflife.org/v3/tree_of_life/node_info"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
HEADERS = {
    "User-Agent": "CladeCanvasBot/0.1 (https://github.com/shesanth/CladeCanvas)"
}

ALL_RANKS = (
    "kingdom", "subkingdom", "infrakingdom",
    "phylum", "subphylum", "infraphylum",
    "superclass", "class", "subclass", "infraclass",
    "superorder", "order", "suborder", "infraorder", "parvorder",
    "superfamily", "family", "subfamily",
    "tribe", "subtribe",
    "genus", "subgenus",
    "species",
)


def get_existing_aliases():
    """Return set of MRCA node_ids that already have a display_name."""
    with Session() as s:
        rows = s.execute(text(
            "SELECT node_id FROM nodes "
            "WHERE node_id LIKE 'mrcaott%' AND display_name IS NOT NULL"
        )).fetchall()
    return {r[0] for r in rows}


def write_aliases(aliases, dry_run=False):
    """Write (mrca_node_id, display_name) pairs to the DB."""
    if not aliases:
        print("No aliases to write.")
        return
    if dry_run:
        print(f"[DRY RUN] Would write {len(aliases)} aliases:")
        for nid, name in aliases[:20]:
            print(f"  {nid} ->{name}")
        if len(aliases) > 20:
            print(f"  ... and {len(aliases) - 20} more")
        return

    with Session() as s:
        for mrca_id, display_name in aliases:
            s.execute(text(
                "UPDATE nodes SET display_name = :name "
                "WHERE node_id = :nid AND display_name IS NULL"
            ), {"name": display_name, "nid": mrca_id})
        s.commit()
    print(f"Wrote {len(aliases)} aliases to DB.")


# ── Phase 1: Wikidata reverse lookup ─────────────────────────────────────────

def _fetch_wikidata_ott_ids(page_size=10000):
    """Paginate through all Wikidata items with P9157 (OTT ID)."""
    all_items = []
    offset = 0
    while True:
        sparql = f"""
SELECT ?item ?itemLabel ?ott WHERE {{
  ?item wdt:P9157 ?ott .
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
}} LIMIT {page_size} OFFSET {offset}
"""
        try:
            r = requests.get(
                WIKIDATA_SPARQL,
                params={"query": sparql, "format": "json"},
                headers=HEADERS, timeout=60,
            )
            r.raise_for_status()
            bindings = r.json().get("results", {}).get("bindings", [])
        except Exception as e:
            print(f"  Wikidata query error at offset {offset}: {e}")
            break

        if not bindings:
            break

        for b in bindings:
            try:
                ott_id = int(b["ott"]["value"])
            except (ValueError, KeyError):
                continue
            label = b.get("itemLabel", {}).get("value", "")
            all_items.append((ott_id, label))

        print(f"  Fetched {offset + len(bindings)} Wikidata P9157 items so far...")
        offset += page_size

        if len(bindings) < page_size:
            break
        time.sleep(1.0)

    return all_items


def phase1_wikidata_reverse(existing, limit=None):
    """Phase 1: Wikidata bulk reverse lookup."""
    print("\n=== Phase 1: Wikidata Reverse Lookup ===")

    # Step 1: Get all OTT IDs from Wikidata
    print("Fetching all OTT IDs from Wikidata (P9157)...")
    wikidata_items = _fetch_wikidata_ott_ids()
    print(f"Got {len(wikidata_items)} Wikidata items with OTT IDs.")

    # Step 2: Filter to taxonomy-only nodes in our DB (num_tips IS NULL)
    ott_to_label = {ott: label for ott, label in wikidata_items}
    ott_ids = list(ott_to_label.keys())

    with Session() as s:
        # Find which of these OTT IDs exist as taxonomy-only nodes
        # (num_tips IS NULL means OTT knows the taxon but synthesis tree doesn't
        # have a dedicated node for it)
        candidates = s.execute(text("""
            SELECT ott_id FROM nodes
            WHERE ott_id = ANY(:ids) AND num_tips IS NULL
        """), {"ids": ott_ids}).fetchall()

    candidate_otts = [r[0] for r in candidates]
    print(f"Found {len(candidate_otts)} taxonomy-only nodes to check against OToL.")

    if limit:
        candidate_otts = candidate_otts[:limit]
        print(f"  (limited to {limit})")

    # Step 3: Query OToL node_info for each candidate
    aliases = []
    errors = 0
    for i, ott_id in enumerate(candidate_otts):
        try:
            resp = requests.post(
                OTOL_API, json={"ott_id": ott_id}, timeout=30
            )
            d = resp.json()
            synth_node_id = d.get("node_id", "")
            if synth_node_id.startswith("mrcaott") and synth_node_id not in existing:
                label = ott_to_label.get(ott_id, f"ott{ott_id}")
                aliases.append((synth_node_id, label))
                existing.add(synth_node_id)
                print(f"  [{i+1}/{len(candidate_otts)}] {label} ->{synth_node_id}")
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  [{i+1}/{len(candidate_otts)}] ott{ott_id} ERROR: {e}")

        if (i + 1) % 100 == 0:
            print(f"  ... progress: {i+1}/{len(candidate_otts)}, "
                  f"{len(aliases)} aliases found")
        time.sleep(0.3)

    print(f"\nPhase 1 done: {len(aliases)} new aliases ({errors} errors).")
    return aliases


# ── Phase 2: Expanded OToL rank query ────────────────────────────────────────

def phase2_expanded_ranks(existing, limit=None):
    """Phase 2: Query OToL node_info for taxonomy-only nodes at all ranks."""
    print("\n=== Phase 2: Expanded Rank Query ===")

    rank_list = ", ".join(f"'{r}'" for r in ALL_RANKS)
    with Session() as s:
        rows = s.execute(text(f"""
            SELECT n.name, n.ott_id, n.rank FROM nodes n
            WHERE n.num_tips IS NULL AND n.ott_id IS NOT NULL
            AND n.name NOT LIKE :pat1 AND n.name NOT LIKE :pat2
            AND n.rank IN ({rank_list})
            ORDER BY array_position(
                ARRAY{list(ALL_RANKS)}::text[], n.rank
            ), n.name
        """), {"pat1": "% sp. %", "pat2": "%BOLD%"}).fetchall()

    print(f"Found {len(rows)} taxonomy-only nodes across all ranks.")
    if limit:
        rows = rows[:limit]
        print(f"  (limited to {limit})")

    aliases = []
    errors = 0
    for i, (name, ott_id, rank) in enumerate(rows):
        try:
            resp = requests.post(
                OTOL_API, json={"ott_id": ott_id}, timeout=30
            )
            d = resp.json()
            synth_node_id = d.get("node_id", "")
            if synth_node_id.startswith("mrcaott") and synth_node_id not in existing:
                aliases.append((synth_node_id, name))
                existing.add(synth_node_id)
                print(f"  [{i+1}/{len(rows)}] {name} ({rank}) ->{synth_node_id}")
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  [{i+1}/{len(rows)}] {name} ERROR: {e}")

        if (i + 1) % 200 == 0:
            print(f"  ... progress: {i+1}/{len(rows)}, "
                  f"{len(aliases)} aliases found")
        time.sleep(0.3)

    print(f"\nPhase 2 done: {len(aliases)} new aliases ({errors} errors).")
    return aliases


# ── Phase 3: Child-pair Wikidata search ──────────────────────────────────────

def phase3_child_pair(existing, limit=500):
    """Phase 3: For top unaliased MRCA nodes, search Wikidata by child taxa."""
    print("\n=== Phase 3: Child-pair Wikidata Search ===")

    import re
    mrca_re = re.compile(r"^mrcaott(\d+)ott(\d+)$")

    with Session() as s:
        rows = s.execute(text("""
            SELECT node_id, num_tips FROM nodes
            WHERE node_id LIKE 'mrcaott%'
            AND display_name IS NULL
            AND num_tips IS NOT NULL
            ORDER BY num_tips DESC
            LIMIT :lim
        """), {"lim": limit}).fetchall()

    print(f"Checking top {len(rows)} unaliased MRCA nodes by num_tips.")

    aliases = []
    errors = 0
    for i, (node_id, num_tips) in enumerate(rows):
        if node_id in existing:
            continue

        m = mrca_re.match(node_id)
        if not m:
            continue
        ott_a, ott_b = int(m.group(1)), int(m.group(2))

        # Look up child taxon names
        with Session() as s:
            name_a = s.execute(text(
                "SELECT name FROM nodes WHERE ott_id = :ott"
            ), {"ott": ott_a}).scalar()
            name_b = s.execute(text(
                "SELECT name FROM nodes WHERE ott_id = :ott"
            ), {"ott": ott_b}).scalar()

        if not name_a or not name_b:
            continue

        # Search Wikidata for a clade/taxon whose P171 (parent taxon) chain
        # or whose label suggests it encompasses both children.
        # Simpler approach: search for items with P9157 matching either child OTT,
        # then check if a parent clade exists that covers both.
        # Actually, the most pragmatic approach: search by label for known
        # clade names that Wikidata has, matching the MRCA's descendant pair.
        sparql = f"""
SELECT ?item ?itemLabel ?ott WHERE {{
  ?item wdt:P9157 ?ott .
  ?item wdt:P171* ?parent .
  ?parent wdt:P9157 "{ott_a}" .
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
}} LIMIT 1
"""
        try:
            r = requests.get(
                WIKIDATA_SPARQL,
                params={"query": sparql, "format": "json"},
                headers=HEADERS, timeout=30,
            )
            bindings = r.json().get("results", {}).get("bindings", [])
            if bindings:
                label = bindings[0].get("itemLabel", {}).get("value", "")
                if label and node_id not in existing:
                    aliases.append((node_id, label))
                    existing.add(node_id)
                    print(f"  [{i+1}] {label} ->{node_id} "
                          f"({name_a} + {name_b}, {num_tips:,} tips)")
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  [{i+1}] {node_id} ERROR: {e}")

        if (i + 1) % 50 == 0:
            print(f"  ... progress: {i+1}/{len(rows)}, "
                  f"{len(aliases)} aliases found")
        time.sleep(1.0)  # be gentle with Wikidata

    print(f"\nPhase 3 done: {len(aliases)} new aliases ({errors} errors).")
    return aliases


# ── Phase 4: Wikidata clade -> MRCA matching ────────────────────────────────

def _get_all_node_ids():
    """Return set of all node_ids in our DB."""
    with Session() as s:
        rows = s.execute(text(
            "SELECT node_id FROM nodes WHERE node_id LIKE 'mrcaott%'"
        )).fetchall()
    return {r[0] for r in rows}


def phase4_wikidata_clades(existing, limit=None):
    """Phase 4: Find Wikidata clades (no OTT ID) and match to MRCA nodes via OToL MRCA API."""
    print("\n=== Phase 4: Wikidata Clade -> MRCA Matching ===")

    MRCA_API = "https://api.opentreeoflife.org/v3/tree_of_life/mrca"
    our_nodes = _get_all_node_ids()

    # Step 1: Query Wikidata for clades without OTT IDs that have children WITH OTT IDs
    sparql = """
SELECT ?item ?itemLabel ?childOtt WHERE {
  ?item wdt:P31 wd:Q713623 .
  FILTER NOT EXISTS { ?item wdt:P9157 ?ott }
  ?child wdt:P171 ?item .
  ?child wdt:P9157 ?childOtt .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
} LIMIT 1000
"""
    print("Querying Wikidata for clades without OTT IDs...")
    try:
        r = requests.get(
            WIKIDATA_SPARQL,
            params={"query": sparql, "format": "json"},
            headers=HEADERS, timeout=120,
        )
        r.raise_for_status()
        bindings = r.json().get("results", {}).get("bindings", [])
    except Exception as e:
        print(f"  Wikidata query error: {e}")
        bindings = []

    # Group by clade
    from collections import defaultdict
    clade_children = defaultdict(lambda: {"label": "", "otts": []})
    for b in bindings:
        qid = b["item"]["value"].rsplit("/", 1)[-1]
        label = b.get("itemLabel", {}).get("value", "")
        try:
            ott = int(b["childOtt"]["value"])
        except (ValueError, KeyError):
            continue
        clade_children[qid]["label"] = label
        clade_children[qid]["otts"].append(ott)

    valid = {k: v for k, v in clade_children.items() if len(v["otts"]) >= 2}
    print(f"Found {len(bindings)} clade-child pairs, {len(valid)} clades with 2+ children.")

    if limit:
        items = list(valid.items())[:limit]
    else:
        items = list(valid.items())

    # Step 2: Compute MRCA for each and match to our DB
    aliases = []
    errors = 0
    for i, (qid, data) in enumerate(items):
        label = data["label"]
        otts = data["otts"][:3]
        try:
            resp = requests.post(MRCA_API, json={"ott_ids": otts}, timeout=30)
            d = resp.json()
            mrca = d.get("mrca", {}).get("node_id", "")
            if (mrca.startswith("mrcaott")
                    and mrca in our_nodes
                    and mrca not in existing):
                aliases.append((mrca, label))
                existing.add(mrca)
                print(f"  {label} -> {mrca}")
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  {label} ERROR: {e}")
        time.sleep(0.3)

    # Step 3: Also try well-known clades that lack Wikidata P171 child links
    # These are verified clade definitions from the phylogenetics literature
    print("\n  Checking well-known unmapped clades...")
    well_known = {
        "Planulozoa": [117569, 641033],       # Bilateria + Cnidaria
        "Nephrozoa": [147604, 189832],         # Deuterostomia + Protostomia
        "ParaHoxozoa": [117569, 570365],       # Bilateria + Placozoa
        "Epitheliozoa": [117569, 67819],       # Bilateria + Porifera
        "Pancrustacea": [955691, 985906],      # Hexapoda + Crustacea (if MRCA)
        "Ecdysozoa": [189832, 395057],         # Protostomia members: Arthropoda + Nematoda
        "Lophotrochozoa": [155737, 801601],    # Mollusca + Annelida
    }
    for name, otts in well_known.items():
        try:
            resp = requests.post(MRCA_API, json={"ott_ids": otts}, timeout=30)
            d = resp.json()
            mrca = d.get("mrca", {}).get("node_id", "")
            if (mrca.startswith("mrcaott")
                    and mrca in our_nodes
                    and mrca not in existing):
                aliases.append((mrca, name))
                existing.add(mrca)
                print(f"  {name} -> {mrca}")
            elif mrca in existing:
                print(f"  {name} -> {mrca} (already aliased)")
            elif not mrca.startswith("mrcaott"):
                print(f"  {name} -> {mrca} (not an MRCA node)")
        except Exception as e:
            print(f"  {name} ERROR: {e}")
        time.sleep(0.3)

    print(f"\nPhase 4 done: {len(aliases)} new aliases ({errors} errors).")
    return aliases


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Discover clade names for synthetic MRCA nodes."
    )
    parser.add_argument(
        "--phase", choices=["1", "2", "3", "4", "all"], default="all",
        help="Which phase to run (default: all)")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview aliases without writing to DB")
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Cap API calls per phase")
    parser.add_argument(
        "--resume", action="store_true", default=True,
        help="Skip MRCA nodes that already have display_name (default: true)")
    args = parser.parse_args()

    existing = get_existing_aliases() if args.resume else set()
    print(f"Starting with {len(existing)} existing aliases.")

    all_aliases = []

    if args.phase in ("1", "all"):
        aliases = phase1_wikidata_reverse(existing, limit=args.limit)
        write_aliases(aliases, dry_run=args.dry_run)
        all_aliases.extend(aliases)

    if args.phase in ("2", "all"):
        aliases = phase2_expanded_ranks(existing, limit=args.limit)
        write_aliases(aliases, dry_run=args.dry_run)
        all_aliases.extend(aliases)

    if args.phase in ("3", "all"):
        lim = args.limit or 500
        aliases = phase3_child_pair(existing, limit=lim)
        write_aliases(aliases, dry_run=args.dry_run)
        all_aliases.extend(aliases)

    if args.phase in ("4", "all"):
        aliases = phase4_wikidata_clades(existing, limit=args.limit)
        write_aliases(aliases, dry_run=args.dry_run)
        all_aliases.extend(aliases)

    print(f"\n{'='*60}")
    print(f"Total new aliases across all phases: {len(all_aliases)}")


if __name__ == "__main__":
    main()
