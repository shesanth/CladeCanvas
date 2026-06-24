from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from cladecanvas.schema import metadata_table, nodes
from cladecanvas.api.models import NodeMetadata, TreeNode
from cladecanvas.api.deps import get_db
from cladecanvas.api.aliases import resolve_node_id, canonicalize_node_row
from cladecanvas.api.hardening import (
    MAX_BULK_NODE_IDS,
    apply_statement_timeout,
    hot_read_cache,
    rate_limit_anonymous_reads,
    set_public_cache_headers,
)
from typing import List

router = APIRouter(dependencies=[Depends(rate_limit_anonymous_reads)])

@router.get("/metadata/{node_id:path}", response_model=NodeMetadata)
def get_node_metadata(node_id: str, response: Response, db: Session = Depends(get_db)):
    set_public_cache_headers(response)

    def load_metadata():
        apply_statement_timeout(db)
        canonical_id = resolve_node_id(db, node_id)
        result = db.execute(select(metadata_table).where(metadata_table.c.node_id == canonical_id)).first()
        if result is None and canonical_id != node_id:
            result = db.execute(select(metadata_table).where(metadata_table.c.node_id == node_id)).first()
        if result is None:
            raise HTTPException(status_code=404, detail="Metadata not found")
        return dict(result._mapping)

    return hot_read_cache.get_or_set(("node_metadata", resolve_node_id(db, node_id)), load_metadata)

@router.get("/bulk", response_model=List[NodeMetadata])
def get_bulk_metadata(
    response: Response,
    node_ids: List[str] = Query(..., min_length=1, max_length=MAX_BULK_NODE_IDS),
    db: Session = Depends(get_db),
):
    set_public_cache_headers(response)
    deduped_ids = tuple(dict.fromkeys(node_ids))

    def load_bulk_metadata():
        apply_statement_timeout(db)
        canonical_ids = tuple(dict.fromkeys(resolve_node_id(db, node_id) for node_id in deduped_ids))
        result = db.execute(select(metadata_table).where(metadata_table.c.node_id.in_(canonical_ids))).fetchall()
        return [dict(row._mapping) for row in result]

    return hot_read_cache.get_or_set(("bulk_metadata", deduped_ids), load_bulk_metadata)

@router.get("/{node_id:path}", response_model=TreeNode)
def get_node_struct(node_id: str, response: Response, db: Session = Depends(get_db)):
    set_public_cache_headers(response)

    def load_node():
        apply_statement_timeout(db)
        canonical_id = resolve_node_id(db, node_id)
        result = db.execute(select(nodes).where(nodes.c.node_id == canonical_id)).first()
        if result is None:
            raise HTTPException(status_code=404, detail="Node not found")
        return canonicalize_node_row(db, dict(result._mapping))

    return hot_read_cache.get_or_set(("node_struct", resolve_node_id(db, node_id)), load_node)
