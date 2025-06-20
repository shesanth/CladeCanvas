from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from cladecanvas.schema import nodes
from cladecanvas.api.models import TreeNode, LineageResponse, SubtreeResponse
from cladecanvas.api.deps import get_db
from typing import List

router = APIRouter()

@router.get("/root", response_model=TreeNode)
def get_root(db: Session = Depends(get_db)):
    result = db.execute(select(nodes).where(nodes.c.parent_ott_id == None)).first()
    if result is None:
        raise HTTPException(status_code=404, detail="Root node not found")
    return result._mapping

@router.get("/children/{parent_id}", response_model=List[TreeNode])
def get_children(parent_id: int, db: Session = Depends(get_db)):
    result = db.execute(select(nodes).where(nodes.c.parent_ott_id == parent_id)).fetchall()
    return [row._mapping for row in result]

@router.get("/lineage/{ott_id}", response_model=LineageResponse)
def get_lineage(ott_id: int, db: Session = Depends(get_db)):
    lineage = []
    current_id = ott_id
    while current_id:
        result = db.execute(select(nodes).where(nodes.c.ott_id == current_id)).first()
        if not result:
            break
        row = result._mapping
        lineage.append(row)
        current_id = row["parent_ott_id"]
    return {"lineage": list(reversed(lineage))}

@router.get("/subtree/{ott_id}", response_model=SubtreeResponse)
def get_subtree(ott_id: int, depth: int = 2, db: Session = Depends(get_db)):
    nodes_result = []
    def recurse(current_id, d):
        if d < 0:
            return
        result = db.execute(select(nodes).where(nodes.c.ott_id == current_id)).first()
        if result:
            nodes_result.append(result._mapping)
        children = db.execute(select(nodes).where(nodes.c.parent_ott_id == current_id)).fetchall()
        for child in children:
            recurse(child.ott_id, d - 1)

    recurse(ott_id, depth)
    return {"nodes": nodes_result}
