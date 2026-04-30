from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from cladecanvas.schema import nodes
from cladecanvas.api.models import TreeNode, LineageResponse, SubtreeResponse
from cladecanvas.api.deps import get_db
from cladecanvas.api.hardening import (
    MAX_CHILDREN_LIMIT,
    MAX_LINEAGE_DEPTH,
    MAX_SUBTREE_DEPTH,
    MAX_SUBTREE_NODES,
    apply_statement_timeout,
    hot_read_cache,
    rate_limit_anonymous_reads,
    set_public_cache_headers,
)
from typing import List

router = APIRouter(dependencies=[Depends(rate_limit_anonymous_reads)])

@router.get("/root", response_model=TreeNode)
def get_root(response: Response, db: Session = Depends(get_db)):
    set_public_cache_headers(response)

    def load_root():
        apply_statement_timeout(db)
        result = db.execute(select(nodes).where(nodes.c.parent_node_id == None)).first()
        if result is None:
            raise HTTPException(status_code=404, detail="Root node not found")
        return dict(result._mapping)

    return hot_read_cache.get_or_set(("tree_root",), load_root)

@router.get("/children/{parent_id:path}", response_model=List[TreeNode])
def get_children(
    parent_id: str,
    response: Response,
    limit: int = Query(100, ge=1, le=MAX_CHILDREN_LIMIT),
    offset: int = Query(0, ge=0, le=10000),
    db: Session = Depends(get_db),
):
    set_public_cache_headers(response)

    def load_children():
        apply_statement_timeout(db)
        total = db.execute(
            select(func.count()).select_from(nodes).where(nodes.c.parent_node_id == parent_id)
        ).scalar_one()
        stmt = (
            select(nodes)
            .where(nodes.c.parent_node_id == parent_id)
            .order_by(nodes.c.node_id)
            .limit(limit)
            .offset(offset)
        )
        result = db.execute(stmt).fetchall()
        children = [dict(row._mapping) for row in result]
        return {"children": children, "total": total}

    payload = hot_read_cache.get_or_set(("children", parent_id, limit, offset), load_children)
    total = payload["total"]
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Limit"] = str(limit)
    response.headers["X-Offset"] = str(offset)
    response.headers["X-Has-More"] = "true" if offset + len(payload["children"]) < total else "false"
    return payload["children"]

@router.get("/lineage/{node_id:path}", response_model=LineageResponse)
def get_lineage(
    node_id: str,
    response: Response,
    max_depth: int = Query(MAX_LINEAGE_DEPTH, ge=1, le=MAX_LINEAGE_DEPTH),
    db: Session = Depends(get_db),
):
    set_public_cache_headers(response)

    def load_lineage():
        return _load_lineage(node_id, max_depth, db)

    return hot_read_cache.get_or_set(("lineage", node_id, max_depth), load_lineage)


def _load_lineage(node_id: str, max_depth: int, db: Session) -> dict[str, list[dict]]:
    apply_statement_timeout(db)
    lineage = []
    current_id = node_id
    seen = set()
    while current_id:
        if current_id in seen:
            raise HTTPException(status_code=422, detail="Cycle detected in lineage")
        if len(lineage) >= max_depth:
            raise HTTPException(status_code=413, detail="Lineage exceeds max_depth")
        seen.add(current_id)
        result = db.execute(select(nodes).where(nodes.c.node_id == current_id)).first()
        if not result:
            break
        row = result._mapping
        lineage.append(dict(row))
        current_id = row["parent_node_id"]
    return {"lineage": list(reversed(lineage))}

@router.get("/subtree/{node_id:path}", response_model=SubtreeResponse)
def get_subtree(
    node_id: str,
    response: Response,
    depth: int = Query(2, ge=0, le=MAX_SUBTREE_DEPTH),
    max_nodes: int = Query(MAX_SUBTREE_NODES, ge=1, le=MAX_SUBTREE_NODES),
    db: Session = Depends(get_db),
):
    set_public_cache_headers(response)

    def load_subtree():
        return _load_subtree(node_id, depth, max_nodes, db)

    return hot_read_cache.get_or_set(("subtree", node_id, depth, max_nodes), load_subtree)


def _load_subtree(node_id: str, depth: int, max_nodes: int, db: Session) -> dict[str, list[dict]]:
    apply_statement_timeout(db)
    nodes_result = []
    def recurse(current_id, d):
        if d < 0:
            return
        if len(nodes_result) >= max_nodes:
            raise HTTPException(status_code=413, detail="Subtree exceeds max_nodes")
        result = db.execute(select(nodes).where(nodes.c.node_id == current_id)).first()
        if result:
            nodes_result.append(dict(result._mapping))
        if d == 0:
            return
        children = (
            db.execute(
                select(nodes)
                .where(nodes.c.parent_node_id == current_id)
                .order_by(nodes.c.node_id)
                .limit(max_nodes - len(nodes_result))
            )
            .fetchall()
        )
        for child in children:
            recurse(child._mapping["node_id"], d - 1)

    recurse(node_id, depth)
    return {"nodes": nodes_result}
