import requests
from datetime import datetime

WIKIDATA_SPARQL = 'https://query.wikidata.org/sparql'
HEADERS = {
    'User-Agent': 'CladeCanvasBot/0.1 (https://github.com/shesanth/CladeCanvas)'
}

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
SELECT ?ott ?item ?itemLabel ?desc ?image ?thumb ?rankLabel WHERE {{
  VALUES ?ott {{ {values} }}
  ?item wdt:P9157 ?ott .
  OPTIONAL {{ ?item schema:description ?desc FILTER(LANG(?desc) = "en") }}
  OPTIONAL {{ ?item wdt:P18 ?image }}
  OPTIONAL {{ ?item wdt:P105 ?rank . ?rank rdfs:label ?rankLabel FILTER(LANG(?rankLabel) = "en") }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
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
        label = b['itemLabel']['value']
        rank = b.get('rankLabel', {}).get('value') if 'rankLabel' in b else None
        full_desc, wiki_page = fetch_wikipedia_extract(q)

        results.append({
            'ott_id': ott,
            'wikidata_q': q,
            'common_name': label,
            'description': short_desc,
            'full_description': full_desc,
            'image_url': image,
            'image_thumb': image,  # currently just duplicating image
            'wiki_page_url': wiki_page,
            'rank': rank,
            'last_updated': datetime.utcnow().isoformat(),
            'enriched_score': 1.0 if full_desc or image else 0.0
        })
    return results