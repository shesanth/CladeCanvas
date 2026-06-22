import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from cladecanvas.api.routes import tree, node, search
from cladecanvas.observability import (
    RequestObservabilityMiddleware,
    configure_logging,
    metrics,
)

configure_logging()

DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]


def get_cors_origins() -> list[str]:
    configured = os.environ.get("CLADECANVAS_CORS_ORIGINS")
    if not configured:
        return DEFAULT_CORS_ORIGINS
    return [origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()]


app = FastAPI(
    title="CladeCanvas API",
    description="API for exploring the tree of life",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Limit", "X-Offset", "X-Has-More"],
)
app.add_middleware(RequestObservabilityMiddleware)

app.include_router(tree.router, prefix="/tree", tags=["Tree"])
app.include_router(node.router, prefix="/node", tags=["Node"])
app.include_router(search.router, prefix="/search", tags=["Search"])


@app.get("/metrics", tags=["Observability"])
def get_metrics():
    return metrics.snapshot()
