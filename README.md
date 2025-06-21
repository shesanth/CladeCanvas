# 🧬 CladeCanvas

**CladeCanvas** is an interactive phylogenetic visualization and exploration tool built as a personal project. Its end goal is to help users understand the structure of life by combining data from the [OpenTree of Life](https://github.com/OpenTreeOfLife/germinator/wiki/Open-Tree-of-Life-Web-APIs) with metadata from **Wikidata** and **Wikipedia**. 

---

## Features

### **Phylogenetic Tree Ingestion**
- Uses `opentree` API to download a subtree for Metazoa (Kingdom Animalia)
- Parses the Newick tree into a flattened CSV (`metazoa_nodes.csv`)
- Extracts `ott_id`, taxon name, and parent-child relationships
- Populates the `nodes` table in a PostgreSQL database

> Tree parsing and csv generation in [`fetch_otol.py`](cladecanvas/fetch_otol.py)

---

### **Metadata Enrichment**
- Enriches taxa with:
  - **Wikidata QIDs**
  - Common names
  - Short + full Wikipedia descriptions
  - Image and thumbnail URLs
  - Wikipedia page URLs
  - Taxonomic `rank` (e.g., species, genus)

>  Parallel workers for populating the DB managed via [`run_workers.py`](scripts/run_workers.py)  
>  Enrichment logic in [`enrich.py`](cladecanvas/enrich.py)

---

### **Exploration & Analysis**

#### [`notebooks/enrichment_overview.ipynb`](notebooks/enrichment_overview.ipynb)
- Visualizes:
  - Enrichment coverage stats
  - Metadata availability (images, descriptions, pages)
  - Display of taxa with thumbnails, descriptions, and ranks

> You can view actual image previews and Wikipedia links for enriched taxa.

---

### **Frontend UI**

![CladeCanvas UI](CladeCanvas_UI.png?)

An interactive React-based visualization built with Next.js (after several hours of pain with Vite) and Tailwind CSS.

- Lazy-loads tree structure as you explore
- Dynamic metadata panel with Wikipedia descriptions and images
- Search by common/scientific name
- Breadcrumb navigation for ancestral lineage

The Dev server starts alongside the API and queries it live for data.

---

### **FastAPI Backend API**

A queryable API for powering the eventual front-end visualization.

#### Core Endpoints
| Endpoint | Description |
|----------|-------------|
| `GET /tree/root` | Get root node |
| `GET /tree/children/{ott_id}` | Immediate children for lazy tree loading |
| `GET /tree/subtree/{ott_id}?depth=N` | Subtree of depth `N` for eager loading |
| `GET /tree/lineage/{ott_id}` | Ancestors from root to this node |
| `GET /node/{ott_id}` | Get a specific node |
| `GET /node/metadata/{ott_id}` | Metadata for a specific node |
| `GET /node/bulk?ott_ids=...` | Batch metadata for many nodes |
| `GET /search?q=...` | Search by name/description |

#### Dev Server
```bash
uvicorn cladecanvas.api.main:app --reload
```
Then visit:
- Swagger: http://127.0.0.1:8000/docs
- ReDoc:   http://127.0.0.1:8000/redoc

#### Example Usage

**Get the root node**
```http
GET /tree/root
```
_Response:_
```json
{
  "ott_id": 691846,
  "name": "Metazoa",
  "parent_ott_id": null,
  "child_count": 24,
  "has_metadata": true
}
```

**Search for a clade by name**
```http
GET /search?q=Eutheria
```
_Response:_
```json
[
 {
    "ott_id": 683263,
    "common_name": "Eutheria",
    "description": "clade of therian mammals",
    "full_description": "...the clade consisting of placental mammals and all therian mammals that are more closely related to placentals than to marsupials.... </p>",
    "image_url": "http://commons.wikimedia.org/wiki/Special:FilePath/Placentalia.jpg",
    "wiki_page_url": "https://en.wikipedia.org/wiki/Eutheria",
    "rank": null,
    "enriched_score": 1
  },
]
```

**Get a specific node**
```http
GET /node/683263
```
_Response:_
```json
{
  "ott_id": 0,
  "name": "string",
  "parent_ott_id": 0,
  "child_count": 0,
  "has_metadata": true
}
```

**Get metadata for a specific node**
```http
GET /node/metadata/683263
```
_Response:_
```json
{
  "ott_id": 683263,
  "common_name": "Eutheria",
  "description": "clade of therian mammals",
  "full_description": "...the clade consisting of placental mammals and all therian mammals that are more closely related to placentals than to marsupials.... </p>",
  "image_url": "http://commons.wikimedia.org/wiki/Special:FilePath/Placentalia.jpg",
  "wiki_page_url": "https://en.wikipedia.org/wiki/Eutheria",
  "rank": null,
  "enriched_score": 1
}
```

**Get lineage (ancestry) for a node**
```http
GET /tree/lineage/683263
```
_Response:_
```json
{
  "lineage": [
    { "ott_id": 691846, "name": "Metazoa" },
    { "ott_id": 641038, "name": "Eumetazoa" },
    { "ott_id": 244265, "name": "Mammalia" },
    { "ott_id": 683263, "name": "Eutheria (in Deuterostomia)" }
  ]
}
```


## How to Run

> **Set the `POSTGRES_URL` environment variable to point to your PostgreSQL instance**

Example:
```bash
export POSTGRES_URL=postgresql://username:password@localhost:5432/cladecanvas
```
Or on Windows:
```cmd
set POSTGRES_URL=postgresql://username:password@localhost:5432/cladecanvas
```

### 1. Load the OpenTree structure and initialize the DB
```bash
python -m scripts.fetch_otol
python -m scripts.populate_db --limit 0 --max-batches 0 # loads CSV into PostgreSQL
```

### 2. Run workers to populate the database
```bash
python -m scripts.run_workers --workers 8 --limit 100 --loops 100 --sleep 2
```

> This will take a long time. There are 2.8M taxa in Metazoa alone, and we respect API limits from Wikidata and Wikipedia.

### 3. Launch API server
```bash
uvicorn cladecanvas.api.main:app --reload
```

### 4. View results in notebook
```bash
jupyter notebook notebooks/enrichment_overview.ipynb
```

### Notebooks Worth Exploring

| Notebook                                                             | Description                                 |
| -------------------------------------------------------------------- | ------------------------------------------- |
| [`enrichment_overview.ipynb`](notebooks/enrichment_overview.ipynb)   | Stats, charts, and displays image previews, descriptions, and links for taxa |

### 5. Front end visualization

> Dev server instructions can be found in in [`cladecanvas/cladecanvas-ui/README.md`](cladecanvas/cladecanvas-ui/README.md). It queries the API server for data.
