from fastapi import APIRouter, Depends, HTTPException, Query
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
from typing import List

router = APIRouter()

NODE_ORDER = (
    desc(func.coalesce(nodes.c.num_tips, -1)),
    func.coalesce(nodes.c.display_name, nodes.c.name),
    nodes.c.node_id,
)

@router.get("/root", response_model=TreeNode)
def get_root(db: Session = Depends(get_db)):
    result = db.execute(select(nodes).where(nodes.c.parent_node_id == None)).first()
    if result is None:
        raise HTTPException(status_code=404, detail="Root node not found")
    return result._mapping

@router.get("/children/{parent_id:path}", response_model=List[TreeNode])
def get_children(parent_id: str, db: Session = Depends(get_db)):
    result = db.execute(select(nodes).where(nodes.c.parent_node_id == parent_id)).fetchall()
    return [row._mapping for row in result]

@router.get("/lineage/{node_id:path}", response_model=LineageResponse)
def get_lineage(node_id: str, db: Session = Depends(get_db)):
    lineage = []
    current_id = node_id
    while current_id:
        result = db.execute(select(nodes).where(nodes.c.node_id == current_id)).first()
        if not result:
            break
        row = result._mapping
        lineage.append(row)
        current_id = row["parent_node_id"]
    return {"lineage": list(reversed(lineage))}

@router.get("/context/{node_id:path}", response_model=ContextGraphResponse)
def get_context_graph(
    node_id: str,
    sibling_limit: int = Query(3, ge=0, le=12),
    child_limit: int = Query(8, ge=0, le=24),
    db: Session = Depends(get_db),
):
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
        row = result._mapping
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
            sibling_row = sibling._mapping
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
        child_row = child._mapping
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
def get_subtree(node_id: str, depth: int = 2, db: Session = Depends(get_db)):
    nodes_result = []
    def recurse(current_id, d):
        if d < 0:
            return
        result = db.execute(select(nodes).where(nodes.c.node_id == current_id)).first()
        if result:
            nodes_result.append(result._mapping)
        children = db.execute(select(nodes).where(nodes.c.parent_node_id == current_id)).fetchall()
        for child in children:
            recurse(child._mapping["node_id"], d - 1)

    recurse(node_id, depth)
    return {"nodes": nodes_result}
