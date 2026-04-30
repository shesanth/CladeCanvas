from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session
from cladecanvas.schema import nodes
from cladecanvas.api.models import (
    ContextGraphResponse,
    TreeNode,
    LineageResponse,
    SubtreeResponse,
)
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

NODE_ORDER = (
    desc(func.coalesce(nodes.c.num_tips, -1)),
    func.coalesce(nodes.c.display_name, nodes.c.name),
    nodes.c.node_id,
)

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

@router.get("/context/{node_id:path}", response_model=ContextGraphResponse)
def get_context_graph(
    node_id: str,
    response: Response,
    sibling_limit: int = Query(3, ge=0, le=12),
    child_limit: int = Query(8, ge=0, le=24),
    db: Session = Depends(get_db),
):
    set_public_cache_headers(response)
    apply_statement_timeout(db)
    lineage = []
    current_id = node_id
    seen = set()
    while current_id:
        if current_id in seen:
            raise HTTPException(status_code=409, detail="Cycle detected in lineage")
        seen.add(current_id)
        result = db.execute(select(nodes).where(nodes.c.node_id == current_id)).first()
        if not result:
            if current_id == node_id:
                raise HTTPException(status_code=404, detail="Node not found")
            break
        row = dict(result._mapping)
        lineage.append(row)
        current_id = row["parent_node_id"]

    lineage = list(reversed(lineage))
    lineage_ids = {row["node_id"] for row in lineage}
    graph_nodes = []
    edges = []
    omitted_by_parent = {}

    def add_node(row, kind, depth, is_focus=False):
        graph_nodes.append({**row, "kind": kind, "depth": depth, "is_focus": is_focus})

    for depth, row in enumerate(lineage):
        add_node(row, "lineage", depth, row["node_id"] == node_id)
        if depth > 0:
            edges.append({
                "source": lineage[depth - 1]["node_id"],
                "target": row["node_id"],
                "kind": "lineage",
            })

    for depth, row in enumerate(lineage[1:], start=1):
        parent_id = row["parent_node_id"]
        if not parent_id or sibling_limit == 0:
            continue

        sibling_rows = db.execute(
            select(nodes)
            .where(nodes.c.parent_node_id == parent_id)
            .where(nodes.c.node_id.not_in(lineage_ids))
            .order_by(*NODE_ORDER)
            .limit(sibling_limit)
        ).fetchall()
        sibling_total = db.execute(
            select(func.count())
            .select_from(nodes)
            .where(nodes.c.parent_node_id == parent_id)
            .where(nodes.c.node_id.not_in(lineage_ids))
        ).scalar_one()
        omitted = max(0, sibling_total - len(sibling_rows))
        if omitted:
            omitted_by_parent[parent_id] = omitted_by_parent.get(parent_id, 0) + omitted
        for sibling in sibling_rows:
            sibling_row = dict(sibling._mapping)
            add_node(sibling_row, "sibling", depth)
            edges.append({
                "source": parent_id,
                "target": sibling_row["node_id"],
                "kind": "sibling",
            })

    child_rows = db.execute(
        select(nodes)
        .where(nodes.c.parent_node_id == node_id)
        .order_by(*NODE_ORDER)
        .limit(child_limit)
    ).fetchall()
    child_total = db.execute(
        select(func.count()).select_from(nodes).where(nodes.c.parent_node_id == node_id)
    ).scalar_one()
    omitted_children = max(0, child_total - len(child_rows))
    if omitted_children:
        omitted_by_parent[node_id] = omitted_by_parent.get(node_id, 0) + omitted_children
    for child in child_rows:
        child_row = dict(child._mapping)
        add_node(child_row, "child", len(lineage))
        edges.append({
            "source": node_id,
            "target": child_row["node_id"],
            "kind": "child",
        })

    return {
        "focus_node_id": node_id,
        "lineage": lineage,
        "nodes": graph_nodes,
        "edges": edges,
        "omitted_by_parent": omitted_by_parent,
    }

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
