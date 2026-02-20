import re
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, or_, case
from sqlalchemy.orm import Session
from cladecanvas.schema import metadata_table
from cladecanvas.api.models import SearchResult
from cladecanvas.api.deps import get_db
from typing import List

router = APIRouter()

SNIPPET_RADIUS = 80


def _extract_snippet(text: str, query: str) -> str:
    """Pull a window around the first match, with '...' on truncated edges."""
    if not text:
        return ""
    match = re.search(re.escape(query), text, re.IGNORECASE)
    if not match:
        return ""
    start = max(0, match.start() - SNIPPET_RADIUS)
    end = min(len(text), match.end() + SNIPPET_RADIUS)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet


@router.get("", response_model=List[SearchResult])
def search_nodes(q: str = Query(..., min_length=2), db: Session = Depends(get_db)):
    c = metadata_table.c
    pattern = f"%{q}%"

    # Tier: common_name > description > full_description
    rank_expr = case(
        (c.common_name.ilike(pattern), 1),
        (c.description.ilike(pattern), 2),
        (c.full_description.ilike(pattern), 3),
    )

    stmt = (
        select(metadata_table, rank_expr.label("_tier"))
        .where(or_(
            c.common_name.ilike(pattern),
            c.description.ilike(pattern),
            c.full_description.ilike(pattern),
        ))
        .order_by(rank_expr, c.node_id)
        .limit(25)
    )
    rows = db.execute(stmt).fetchall()

    results = []
    for row in rows:
        m = row._mapping
        tier = m["_tier"]
        if tier == 1:
            match_field = "common_name"
            snippet = m["common_name"] or ""
        elif tier == 2:
            match_field = "description"
            snippet = m["description"] or ""
        else:
            match_field = "full_description"
            snippet = _extract_snippet(m["full_description"] or "", q)

        results.append(SearchResult(
            node_id=m["node_id"],
            ott_id=m["ott_id"],
            common_name=m["common_name"],
            description=m["description"],
            image_url=m["image_url"],
            wiki_page_url=m["wiki_page_url"],
            enriched_score=m["enriched_score"],
            match_field=match_field,
            match_snippet=snippet,
        ))
    return results
