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
  db.py                # Engine / session factory (Postgres or read-only dev SQLite)
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
- PostgreSQL for full data loading/enrichment
- Node.js 18+

For API/frontend development without a local PostgreSQL database, set
`CLADECANVAS_DEV_SQLITE=1`. The API will use the checked-in
`data/dev_seed.sqlite` fixture in read-only mode.

## Developer SQLite Mode

CladeCanvas has three database profiles:

| Profile | How it is selected | Write behavior |
|---------|--------------------|----------------|
| `prod` | `CLADECANVAS_DB_PROFILE=prod` with `POSTGRES_URL` | Full PostgreSQL read/write |
| `dev-postgres` | Default when `POSTGRES_URL` is set | Full PostgreSQL read/write |
| `dev-sqlite` | `CLADECANVAS_DEV_SQLITE=1` or `CLADECANVAS_DB_PROFILE=dev-sqlite` | Read-only seed DB |

Use `dev-sqlite` when you only need local API/frontend reads:

```bash
CLADECANVAS_DEV_SQLITE=1 uvicorn cladecanvas.api.main:app --port 8600 --reload
```

On Windows PowerShell:

```powershell
$env:CLADECANVAS_DEV_SQLITE = "1"
uvicorn cladecanvas.api.main:app --port 8600 --reload
```

In this mode `POSTGRES_URL` is not required. The API opens
`data/dev_seed.sqlite` through SQLite's read-only URI mode, so accidental
database writes fail at the database layer. Startup logs include a clear
database-mode banner such as `CladeCanvas database mode: dev-sqlite
(read-only API seed; enrichment/write paths disabled)`.

The checked-in seed is intentionally tiny. It exists to prove and exercise the
read-only routes used by local development and CI:

- `GET /tree/root`
- `GET /node/{node_id}`
- `GET /node/metadata/{node_id}`
- `GET /search?q=...`

Write-oriented paths are blocked explicitly in `dev-sqlite`: database
population, enrichment workers, metadata repair, and MRCA alias write scripts
raise a clear `RuntimeError` before doing work. Use PostgreSQL for those jobs.

To point at a different local seed file:

```bash
CLADECANVAS_DEV_SQLITE=1 CLADECANVAS_SQLITE_PATH=/path/to/dev_seed.sqlite uvicorn cladecanvas.api.main:app --port 8600 --reload
```

Run the SQLite smoke tests with:

```bash
CLADECANVAS_DEV_SQLITE=1 pytest -m api tests/test_dev_sqlite_api.py -q
```

## How to Build the Database

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure the database connection

For full database loading and enrichment, set the `POSTGRES_URL` environment
variable:

```bash
export POSTGRES_URL=postgresql://user:pass@localhost:5432/cladecanvas
```

On Windows:
```cmd
set POSTGRES_URL=postgresql://user:pass@localhost:5432/cladecanvas
```

Or create a `.env` file in the project root (loaded automatically by `python-dotenv`).

For read-only local API/frontend development, use the tiny SQLite seed instead:

```bash
export CLADECANVAS_DEV_SQLITE=1
uvicorn cladecanvas.api.main:app --port 8600 --reload
```

On Windows PowerShell:
```powershell
$env:CLADECANVAS_DEV_SQLITE = "1"
uvicorn cladecanvas.api.main:app --port 8600 --reload
```

This mode does not require `POSTGRES_URL`. It serves `/tree/root`,
`/node/{node_id}`, `/node/metadata/{node_id}`, and `/search` from
`data/dev_seed.sqlite`; enrichment, population, metadata repair, and MRCA alias
write scripts fail immediately with a clear `RuntimeError`. Set
`CLADECANVAS_SQLITE_PATH` to point at a different seed file if needed.

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

Use `CLADECANVAS_DEV_SQLITE=1` with the same command when you only need the
read-only seed API.

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
