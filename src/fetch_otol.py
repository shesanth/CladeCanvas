import os
import csv
import re
import dendropy
from opentree import OT

TAXON = 'Metazoa'
OTT_ID = 691846
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
RAW_PATH = os.path.join(DATA_DIR, f'{TAXON.lower()}.newick')
CSV_PATH = os.path.join(DATA_DIR, f'{TAXON.lower()}_nodes.csv')

ID_RE = re.compile(r'ott(\d+)', re.IGNORECASE)
CLEAN_RE = re.compile(r'[ _]?ott\d+', re.IGNORECASE)
DUP_RE = re.compile(r'^(?P<name>.+?)\s+\1$')


def download_taxonomy():
    os.makedirs(DATA_DIR, exist_ok=True)
    subtree = OT.taxon_subtree(ott_id=OTT_ID)
    newick = subtree.response_dict.get('newick') or getattr(subtree, 'newick', '')
    if not newick:
        raise RuntimeError('could not get newick from API')
    with open(RAW_PATH, 'w', encoding='utf-8') as f:
        f.write(newick)


def flatten_newick():
    with open(RAW_PATH, 'r', encoding='utf-8', errors='replace') as f:
        newick_data = f.read()
    tree = dendropy.Tree.get(data=newick_data,
                              schema='newick',
                              preserve_underscores=True)
    rows = []
    traverse_and_generate_rows(tree.seed_node, None, rows)
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['ott_id', 'name', 'parent_ott_id'])
        writer.writeheader()
        writer.writerows(rows)

def traverse_and_generate_rows(node, parent_id, rows):
    # Try to get label from species or higher taxa
    label = node.taxon.label if node.taxon else node.label or ''
    matches = ID_RE.findall(label)
    ott_id = int(matches[-1]) if matches else None
    name = CLEAN_RE.sub('', label).replace('_', ' ').strip()
    dup = DUP_RE.match(name)
    if dup:
        name = dup.group('name')
    rows.append({'ott_id': ott_id, 'name': name, 'parent_ott_id': parent_id})
    for child in node.child_node_iter():
        next_parent_id = ott_id if ott_id is not None else parent_id
        traverse_and_generate_rows(child, next_parent_id, rows)

def main():
    if not os.path.exists(RAW_PATH):
        print(f'Downloading taxonomy subtree for {TAXON}…')
        download_taxonomy()
    print('Generating CSV…')
    flatten_newick()
    print(f'CSV saved to {CSV_PATH}')

if __name__ == '__main__':
    main()
