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
  discover_mrca_names.py # Maps taxonomy names onto synthetic MRCA nodes
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

Schema changes are managed with [Alembic](https://alembic.sqlalchemy.org/):

```bash
alembic revision --autogenerate -m "describe your change"  # generate migration
alembic upgrade head                                        # apply migrations
alembic check                                               # verify no drift
```

Verify the indexes required by the hot API read paths before promoting a database:

```bash
python scripts/verify_db_indexes.py
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

Maps familiar taxonomy names (e.g. "Arachnida", "Planulozoa") onto synthetic MRCA nodes. Runs in four phases: OToL node_info lookups, child-based matching, Wikidata cross-referencing, and MRCA computation for clades without OTT IDs.

```bash
python scripts/discover_mrca_names.py --phase all --dry-run  # preview
python scripts/discover_mrca_names.py --phase all             # write to DB
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

Anonymous read endpoints are rate-limited per client. Hot read responses include public cache headers and a short in-process cache. Deployment knobs:

| Variable | Default | Purpose |
|----------|---------|---------|
| `CLADECANVAS_ANON_READS_PER_MINUTE` | `120` | Anonymous GET requests allowed per client per minute |
| `CLADECANVAS_QUERY_TIMEOUT_MS` | `3000` | Postgres statement timeout applied to API reads |
| `CLADECANVAS_PUBLIC_CACHE_SECONDS` | `60` | Browser/proxy cache max-age for read responses |
| `CLADECANVAS_HOT_READ_CACHE_SECONDS` | `30` | In-process cache TTL for hot read payloads |
| `CLADECANVAS_MAX_BULK_NODE_IDS` | `100` | Maximum IDs accepted by `/node/bulk` |
| `CLADECANVAS_MAX_CHILDREN_LIMIT` | `200` | Maximum page size for `/tree/children/{node_id}` |
| `CLADECANVAS_MAX_SEARCH_LIMIT` | `50` | Maximum page size for `/search` |
| `CLADECANVAS_MAX_LINEAGE_DEPTH` | `128` | Maximum lineage traversal depth |
| `CLADECANVAS_MAX_SUBTREE_DEPTH` | `4` | Maximum subtree traversal depth |
| `CLADECANVAS_MAX_SUBTREE_NODES` | `500` | Maximum nodes returned by `/tree/subtree/{node_id}` |

### Tree

| Endpoint | Description |
|----------|-------------|
| `GET /tree/root` | Root node of the tree |
| `GET /tree/children/{node_id}?limit=100&offset=0` | Immediate children of a node |
| `GET /tree/subtree/{node_id}?depth=N&max_nodes=500` | Subtree rooted at a node to depth N |
| `GET /tree/lineage/{node_id}?max_depth=128` | Ancestor chain from root to node |

`/tree/children/{node_id}` keeps its list response shape for compatibility. The response includes `X-Total-Count`,
`X-Limit`, `X-Offset`, and `X-Has-More` headers so clients can tell when a page is truncated and request additional
pages explicitly.

### Node

| Endpoint | Description |
|----------|-------------|
| `GET /node/{node_id}` | Node structure (name, parent, child_count, num_tips, display_name) |
| `GET /node/metadata/{node_id}` | Enriched metadata (common name, description, image, Wikipedia link) |
| `GET /node/bulk?node_ids=...` | Batch metadata for multiple nodes, capped by `CLADECANVAS_MAX_BULK_NODE_IDS` |

### Search

| Endpoint | Description |
|----------|-------------|
| `GET /search?q=...&limit=25&offset=0` | Search metadata by common name or description |

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
