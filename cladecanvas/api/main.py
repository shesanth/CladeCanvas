from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from cladecanvas.api.routes import tree, node, search

app = FastAPI(
    title="CladeCanvas API",
    description="API for exploring the tree of life",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # Replace to whatever frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tree.router, prefix="/tree", tags=["Tree"])
app.include_router(node.router, prefix="/node", tags=["Node"])
app.include_router(search.router, prefix="/search", tags=["Search"])
