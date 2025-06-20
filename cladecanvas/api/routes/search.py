from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from cladecanvas.schema import metadata_table
from cladecanvas.api.models import NodeMetadata
from cladecanvas.api.deps import get_db
from typing import List

router = APIRouter()

@router.get("", response_model=List[NodeMetadata])
def search_nodes(q: str = Query(...), db: Session = Depends(get_db)):
    stmt = select(metadata_table).where(
        or_(
            metadata_table.c.common_name.ilike(f"%{q}%"),
            metadata_table.c.description.ilike(f"%{q}%"),
            metadata_table.c.full_description.ilike(f"%{q}%")
        )
    ).limit(25)
    results = db.execute(stmt).fetchall()
    return [row._mapping for row in results]
