from fastapi import FastAPI
from cladecanvas.api.routes import tree, node, search

app = FastAPI(
    title="CladeCanvas API",
    description="API for exploring the tree of life and enriched metadata",
    version="0.1.0"
)

app.include_router(tree.router, prefix="/tree", tags=["Tree"])
app.include_router(node.router, prefix="/node", tags=["Node"])
app.include_router(search.router, prefix="/search", tags=["Search"])
