"""
Prototype/MVP script to enrich node taxa with metadata from Wikidata and Wikipedia.
"""
import os
import sqlite3
import pandas as pd
import requests

script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(script_dir, '..'))
DATA_DIR = os.path.join(project_root, 'data')
CSV_PATH = os.path.join(DATA_DIR, 'metazoa_nodes.csv')
DB_PATH = os.path.join(DATA_DIR, 'metazoa.db')

WIKIDATA_SPARQL = 'https://query.wikidata.org/sparql'
HEADERS = {
    'User-Agent': 'CladeCanvasBot/0.1 (https://github.com/shesanth/CladeCanvas)'
}


def initialize_db(db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS nodes (
            ott_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            parent_ott_id INTEGER
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS metadata (
            ott_id INTEGER PRIMARY KEY,
            wikidata_q TEXT,
            common_name TEXT,
            description TEXT,
            full_description TEXT,
            image_url TEXT,
            wiki_page_url TEXT
        )
    ''')
    conn.commit()

    try:
        c.execute("ALTER TABLE metadata ADD COLUMN full_description TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE metadata ADD COLUMN wiki_page_url TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    return conn


def load_nodes(conn, csv_path):
    df = pd.read_csv(csv_path, dtype={'ott_id': pd.Int64Dtype(), 'parent_ott_id': pd.Int64Dtype()})
    records = df.dropna(subset=['ott_id']).to_dict('records')
    with conn:
        conn.executemany(
            'INSERT OR IGNORE INTO nodes (ott_id, name, parent_ott_id) VALUES (:ott_id, :name, :parent_ott_id)',
            records
        )


def fetch_wikipedia_extract(wikidata_q):
    url = 'https://www.wikidata.org/w/api.php'
    params = {
        'action': 'wbgetentities',
        'ids': wikidata_q,
        'format': 'json',
        'props': 'sitelinks'
    }
    r = requests.get(url, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    entities = r.json().get('entities', {})
    sitelinks = entities.get(wikidata_q, {}).get('sitelinks', {})
    title = sitelinks.get('enwiki', {}).get('title')
    if not title:
        return None, None

    wiki_page_url = f'https://en.wikipedia.org/wiki/{title.replace(" ", "_")}'

    wiki_url = 'https://en.wikipedia.org/w/api.php'
    wiki_params = {
        'action': 'query',
        'prop': 'extracts',
        'exintro': True,
        'titles': title,
        'format': 'json',
        'formatversion': 2
    }
    wiki_r = requests.get(wiki_url, params=wiki_params, headers=HEADERS, timeout=30)
    wiki_r.raise_for_status()
    pages = wiki_r.json().get('query', {}).get('pages', [])
    if pages and 'extract' in pages[0]:
        text = pages[0]['extract']
        clean = ' '.join(text.split())
        return clean, wiki_page_url
    return None, wiki_page_url


def fetch_wikidata(ott_ids):
    values = ' '.join(f'"{i}"' for i in ott_ids)
    sparql = f"""
    SELECT ?ott ?item ?itemLabel ?desc ?image WHERE {{
      VALUES ?ott {{ {values} }}
      ?item wdt:P9157 ?ott .
      OPTIONAL {{ ?item schema:description ?desc FILTER(LANG(?desc) = \"en\") }}
      OPTIONAL {{ ?item wdt:P18 ?image }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language \"en\" }}
    }}
    """
    r = requests.get(WIKIDATA_SPARQL, params={'query': sparql, 'format': 'json'}, headers=HEADERS, timeout=60)
    r.raise_for_status()
    data = r.json().get('results', {}).get('bindings', [])

    results = []
    for b in data:
        ott = int(b['ott']['value'])
        q = b['item']['value'].rsplit('/', 1)[-1]
        short_desc = b.get('desc', {}).get('value')
        image = b.get('image', {}).get('value')
        label = b.get('itemLabel', {}).get('value')
        full_desc, wiki_page = fetch_wikipedia_extract(q)
        results.append({
            'ott_id': ott,
            'wikidata_q': q,
            'common_name': label,
            'description': short_desc,
            'full_description': full_desc,
            'image_url': image,
            'wiki_page_url': wiki_page,
        })
    return results



def load_metadata(conn, metadata):
    with conn:
        conn.executemany(
            '''
            INSERT OR REPLACE INTO metadata
                (ott_id, wikidata_q, common_name, description,
                 full_description, image_url, wiki_page_url)
            VALUES
                (:ott_id, :wikidata_q, :common_name, :description,
                 :full_description, :image_url, :wiki_page_url)
            ''',
            metadata
        )


if __name__ == '__main__':
    conn = initialize_db(DB_PATH)
    print('Loading nodes...')
    load_nodes(conn, CSV_PATH)

    cur = conn.cursor()
    cur.execute(
        'SELECT ott_id FROM nodes WHERE ott_id NOT IN (SELECT ott_id FROM metadata) ORDER BY RANDOM() LIMIT 100'
    )
    batch = [row[0] for row in cur.fetchall()]
    if batch:
        print(f'Fetching metadata for {len(batch)} taxa...')
        md = fetch_wikidata(batch)
        load_metadata(conn, md)
        print('Metadata loaded.')
    else:
        print('No new taxa to enrich with metadata.')
    conn.close()
