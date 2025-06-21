from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from cladecanvas.schema import metadata_table, nodes
from cladecanvas.api.models import NodeMetadata, TreeNode
from cladecanvas.api.deps import get_db
from typing import List

router = APIRouter()

@router.get("/{ott_id}", response_model=TreeNode)
def get_node_struct(ott_id: int, db: Session = Depends(get_db)):
    result = db.execute(select(nodes).where(nodes.c.ott_id == ott_id)).first()
    if result is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return result._mapping

@router.get("/metadata/{ott_id}", response_model=NodeMetadata)
def get_node_metadata(ott_id: int, db: Session = Depends(get_db)):
    result = db.execute(select(metadata_table).where(metadata_table.c.ott_id == ott_id)).first()
    if result is None:
        raise HTTPException(status_code=404, detail="Metadata not found")
    return result._mapping

@router.get("/bulk", response_model=List[NodeMetadata])
def get_bulk_metadata(ott_ids: List[int] = Query(...), db: Session = Depends(get_db)):
    result = db.execute(select(metadata_table).where(metadata_table.c.ott_id.in_(ott_ids))).fetchall()
    return [row._mapping for row in result]
