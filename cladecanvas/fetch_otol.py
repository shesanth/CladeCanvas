import os
import csv
import re
import sys
import time
import requests

TAXON = 'Metazoa'
OTT_ID = 691846
API_URL = 'https://api.opentreeoflife.org/v3/tree_of_life'
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
CSV_PATH = os.path.join(DATA_DIR, f'{TAXON.lower()}_nodes_synth.csv')

MRCA_RE = re.compile(r'^mrcaott\d+ott\d+$', re.IGNORECASE)
ARGUSON_DEPTH = 20  # levels per API call

# Increase recursion limit for deep arguson trees
sys.setrecursionlimit(10000)


def _arguson_subtree(node_id: str, height_limit: int = ARGUSON_DEPTH) -> dict | None:
    """Fetch arguson tree structure for a node."""
    payload = {'height_limit': height_limit, 'format': 'arguson'}
    if node_id.startswith('ott') and not node_id.startswith('mrcaott'):
        payload['ott_id'] = int(node_id[3:])
    else:
        payload['node_id'] = node_id
    try:
        resp = requests.post(f'{API_URL}/subtree', json=payload, timeout=300)
        if resp.ok:
            return resp.json().get('arguson')
    except Exception as e:
        print(f'  Error fetching {node_id}: {e}')
    return None


def _parse_arguson(node: dict, parent_node_id: str | None,
                   rows: list, seen: set, frontier: list):
    """Recursively parse an arguson node tree into flat rows.

    Nodes that are truncated (have num_tips > 1 but no children in response)
    are added to frontier for the next wave.
    """
    nid = node.get('node_id', '')
    if not nid:
        return

    # Record this node if not seen
    is_new = nid not in seen
    if is_new:
        seen.add(nid)
        taxon = node.get('taxon', {})
        ott_id = taxon.get('ott_id')
        name = taxon.get('name', nid)
        rows.append({
            'node_id': nid,
            'ott_id': ott_id,
            'name': name,
            'parent_node_id': parent_node_id,
        })

    # Process children if present in response
    children = node.get('children')
    if children is not None:
        for child in children:
            _parse_arguson(child, nid, rows, seen, frontier)
    else:
        # No children in response — check if truncated (has sub-tree we haven't explored)
        num_tips = node.get('num_tips', 0)
        if num_tips > 1:
            frontier.append(nid)


def download_synth_arguson():
    """Download the Metazoa synthesis tree using arguson format for efficiency."""
    os.makedirs(DATA_DIR, exist_ok=True)
    rows = []
    seen = set()

    root_id = f'ott{OTT_ID}'
    frontier = [root_id]
    wave = 0

    while frontier:
        wave += 1
        current_batch = frontier
        frontier = []
        print(f'\n=== Wave {wave}: {len(current_batch)} nodes to expand ===')

        for i, nid in enumerate(current_batch):
            print(f'  [{i+1}/{len(current_batch)}] Fetching {nid}...')
            arguson = _arguson_subtree(nid)
            if arguson:
                n_before = len(rows)
                # For the root of each fetch, use the parent we already recorded
                # (except for the very first fetch where parent is None)
                existing_parent = None
                for r in rows:
                    if r['node_id'] == nid:
                        existing_parent = r['parent_node_id']
                        break
                _parse_arguson(arguson, existing_parent, rows, seen, frontier)
                print(f'    +{len(rows) - n_before} nodes (total: {len(rows):,})')
            else:
                print(f'    WARNING: no data for {nid}')
            time.sleep(0.3)

        n_synth = sum(1 for r in rows if r['ott_id'] is None)
        print(f'  Wave {wave} done. {len(rows):,} nodes ({n_synth:,} synthetic). '
              f'Next frontier: {len(frontier)}')

    # Write CSV
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['node_id', 'ott_id', 'name', 'parent_node_id'])
        writer.writeheader()
        writer.writerows(rows)
    n_synth = sum(1 for r in rows if r['ott_id'] is None)
    print(f'\nCSV saved to {CSV_PATH}  ({len(rows):,} nodes, {n_synth:,} synthetic)')


def main():
    print('Downloading synthesis tree via arguson...')
    download_synth_arguson()


if __name__ == '__main__':
    main()
