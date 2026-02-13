from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from cladecanvas.schema import metadata_table, nodes
from cladecanvas.api.models import NodeMetadata, TreeNode
from cladecanvas.api.deps import get_db
from typing import List

router = APIRouter()

@router.get("/metadata/{node_id:path}", response_model=NodeMetadata)
def get_node_metadata(node_id: str, db: Session = Depends(get_db)):
    result = db.execute(select(metadata_table).where(metadata_table.c.node_id == node_id)).first()
    if result is None:
        raise HTTPException(status_code=404, detail="Metadata not found")
    return result._mapping

@router.get("/bulk", response_model=List[NodeMetadata])
def get_bulk_metadata(node_ids: List[str] = Query(...), db: Session = Depends(get_db)):
    result = db.execute(select(metadata_table).where(metadata_table.c.node_id.in_(node_ids))).fetchall()
    return [row._mapping for row in result]

@router.get("/{node_id:path}", response_model=TreeNode)
def get_node_struct(node_id: str, db: Session = Depends(get_db)):
    result = db.execute(select(nodes).where(nodes.c.node_id == node_id)).first()
    if result is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return result._mapping
