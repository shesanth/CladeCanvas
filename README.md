# CladeCanvas

CladeCanvas is an interactive phylogenetic visualization and exploration tool. It combines data from the [Open Tree of Life](https://github.com/OpenTreeOfLife/germinator/wiki/Open-Tree-of-Life-Web-APIs) synthesis tree with metadata from Wikidata and Wikipedia to let users navigate the structure of animal life.

![CladeCanvas UI](CladeCanvas_UI.png)

## Features

- Lazy-loading tree sidebar with expand-in-place navigation
- Metadata panel with Wikipedia descriptions, images, and links
- Search by common name or description
- Breadcrumb lineage trail with collapsed synthetic node runs
- Readable labels for synthetic MRCA branching points (e.g. "Bilateria + Porifera")
- Taxonomy-based aliases for MRCA nodes (e.g. "Arachnida" for `mrcaott343ott948`)
- Auto-scroll to active node in the tree sidebar

## Architecture

```
cladecanvas/
  fetch_otol.py        # Downloads the OToL synthesis tree via arguson API
  enrich.py            # Wikidata SPARQL + Wikipedia enrichment
  schema.py            # SQLAlchemy table definitions (nodes, metadata)
  db.py                # Engine / session factory (reads POSTGRES_URL)
  api/
    main.py            # FastAPI app with CORS
    routes/            # tree, node, search endpoints
  cladecanvas-ui/      # Next.js + Tailwind frontend

scripts/
  populate_db.py       # Loads CSV into PostgreSQL, runs enrichment
  run_workers.py       # Parallel enrichment workers
  alias_mrca_nodes.py  # Maps taxonomy names onto synthetic MRCA nodes
```

The synthesis tree contains ~1.7M nodes under Metazoa, including ~65K synthetic MRCA nodes that represent branching points without a corresponding taxon in the OToL taxonomy.

## Prerequisites

- Python 3.11+
- PostgreSQL
- Node.js 18+

## How to Build the Database

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure the database connection

The application raises a `RuntimeError` at startup if `POSTGRES_URL` is missing.

Set the `POSTGRES_URL` environment variable:

```bash
export POSTGRES_URL=postgresql://user:pass@localhost:5432/cladecanvas
```

On Windows:
```cmd
set POSTGRES_URL=postgresql://user:pass@localhost:5432/cladecanvas
```

Or create a `.env` file in the project root (loaded automatically by `python-dotenv`).

### 3. Download the synthesis tree

Fetches the Metazoa subtree from the OToL arguson API and writes `data/metazoa_nodes_synth.csv`. Takes roughly 45 minutes due to API rate limits.

```bash
python -m cladecanvas.fetch_otol
```

The download proceeds in waves — each wave expands truncated nodes from the previous one until the full tree is captured. Synthetic MRCA nodes get readable names derived from `descendant_name_list` (e.g. "Bilateria + Porifera" instead of `mrcaott42ott3989`).

### 4. Load nodes into PostgreSQL

```bash
python -m scripts.populate_db --skip-enrich
```

This creates the `nodes` and `metadata` tables, then upserts all rows from the CSV. On subsequent runs it updates `name`, `num_tips`, and `parent_node_id` for existing nodes.

If migrating from an older schema that used `ott_id` as the primary key:
```bash
python -m scripts.populate_db --migrate --skip-enrich
```

### 5. Enrich with Wikidata and Wikipedia

Single-threaded (good for small batches):
```bash
python -m scripts.populate_db --limit 100 --max-batches 10
```

Parallel (faster, respects API rate limits):
```bash
python -m scripts.run_workers --workers 8 --limit 100 --loops 100 --sleep 2
```

Enrichment queries Wikidata for common names, descriptions, images, and taxonomic rank, then fetches Wikipedia introductions. There are ~1.7M taxon nodes, so full enrichment is a long-running process.

### 6. Alias MRCA nodes (optional)

Maps familiar taxonomy names (e.g. "Arachnida", "Rotifera") onto synthetic MRCA nodes by querying the OToL `node_info` API. Taxa whose synthesis tree placement is a synthetic node get their name stored as `display_name`.

```bash
python scripts/alias_mrca_nodes.py
```

## Running the Application

### API server

```bash
uvicorn cladecanvas.api.main:app --port 8600 --reload
```

- Swagger docs: http://localhost:8600/docs
- ReDoc: http://localhost:8600/redoc

### Frontend

```bash
cd cladecanvas/cladecanvas-ui
npm install
npm run dev
```

Create `cladecanvas/cladecanvas-ui/.env.local` if it doesn't exist:
```
NEXT_PUBLIC_API_BASE=http://localhost:8600
```

Then visit http://localhost:3000.

## API Endpoints

All node identifiers are strings: `ott{N}` for taxon nodes, `mrcaott{A}ott{B}` for synthetic nodes.

### Tree

| Endpoint | Description |
|----------|-------------|
| `GET /tree/root` | Root node of the tree |
| `GET /tree/children/{node_id}` | Immediate children of a node |
| `GET /tree/subtree/{node_id}?depth=N` | Subtree rooted at a node to depth N |
| `GET /tree/lineage/{node_id}` | Ancestor chain from root to node |

### Node

| Endpoint | Description |
|----------|-------------|
| `GET /node/{node_id}` | Node structure (name, parent, child_count, num_tips, display_name) |
| `GET /node/metadata/{node_id}` | Enriched metadata (common name, description, image, Wikipedia link) |
| `GET /node/bulk?node_ids=...` | Batch metadata for multiple nodes |

### Search

| Endpoint | Description |
|----------|-------------|
| `GET /search?q=...` | Search metadata by common name or description |

## Database Schema

### `nodes`

| Column | Type | Notes |
|--------|------|-------|
| `node_id` | TEXT PK | `ott{N}` or `mrcaott{A}ott{B}` |
| `ott_id` | INTEGER | OTT taxonomy ID (NULL for synthetic nodes) |
| `name` | TEXT | Taxon name or synthesized label from `descendant_name_list` |
| `parent_node_id` | TEXT | Parent node reference |
| `rank` | TEXT | Taxonomic rank (set during enrichment) |
| `child_count` | INTEGER | Number of direct children |
| `has_metadata` | INTEGER | 1 if enriched metadata exists |
| `num_tips` | INTEGER | Descendant species count from synthesis tree |
| `display_name` | TEXT | Taxonomy alias for MRCA nodes (set by `alias_mrca_nodes.py`) |

### `metadata`

| Column | Type | Notes |
|--------|------|-------|
| `node_id` | TEXT PK, FK | References `nodes.node_id` |
| `ott_id` | INTEGER | OTT taxonomy ID |
| `wikidata_q` | TEXT | Wikidata QID |
| `common_name` | TEXT | English common name from Wikidata |
| `description` | TEXT | Short Wikidata description |
| `full_description` | TEXT | Wikipedia introduction (HTML) |
| `image_url` | TEXT | Wikimedia Commons image URL |
| `wiki_page_url` | TEXT | Wikipedia article URL |
| `enriched_score` | FLOAT | 1.0 if description or image exists, else 0.0 |

## Exploration

The Jupyter notebook at [`notebooks/enrichment_overview.ipynb`](notebooks/enrichment_overview.ipynb) visualizes enrichment coverage, metadata availability, and displays image previews for enriched taxa.

```bash
jupyter notebook notebooks/enrichment_overview.ipynb
```
