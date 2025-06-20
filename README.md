# 🧬 CladeCanvas

**CladeCanvas** is a personal project intended to be an interactive phylogenetic visualization and exploration tool. Its end goal is to help users understand the structure of life by combining data from the [OpenTree of Life](https://opentreeoflife.org/) with metadata from **Wikidata** and **Wikipedia**.

---

##  What It Currently Does

### 1. **Phylogenetic Tree Ingestion**
- Uses `opentree` API to download a subtree for Metazoa (Kingdom Animalia)
- Parses the Newick tree into a flattened CSV (`metazoa_nodes.csv`)
- Extracts `ott_id`, taxon name, and parent-child relationships
- Populates the `nodes` table in a PostgreSQL database

> Tree parsing and csv generation in [`fetch_otol.py`](cladecanvas/fetch_otol.py)

---

### 2. **Metadata Enrichment**
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

### 3. **Exploration & Analysis**

#### [`notebooks/enrichment_overview.ipynb`](notebooks/enrichment_overview.ipynb)
- Visualizes:
  - Enrichment coverage stats
  - Metadata availability (images, descriptions, pages)
  - Display of taxa with thumbnails, descriptions, and ranks

> You can view actual image previews and Wikipedia links for enriched taxa.


## How to Run

### 1. Load the OpenTree structure and initialize the DB
```bash
python -m scripts.fetch_otol
python -m scripts.populate_db  # loads CSV into PostgreSQL
```

### 2. Run workers to populate the database in background

```bash
python -m scripts.run_workers --workers 8 --limit 100 --loops 100 --sleep 2
```
### 3. View results in notebook

```bash
jupyter notebook notebooks/enrichment_overview.ipynb
```

### Notebooks Worth Exploring

| Notebook                                                             | Description                                 |
| -------------------------------------------------------------------- | ------------------------------------------- |
| [`enrichment_overview.ipynb`](notebooks/enrichment_overview.ipynb)   | Stats, charts, and displays image previews, descriptions, and links for taxa |
