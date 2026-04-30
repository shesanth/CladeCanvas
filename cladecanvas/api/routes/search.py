from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import case, func, literal, or_, select
from sqlalchemy.orm import Session
from typing import List

from cladecanvas.api.deps import get_db
from cladecanvas.api.hardening import (
    MAX_SEARCH_LIMIT,
    apply_statement_timeout,
    hot_read_cache,
    rate_limit_anonymous_reads,
    set_public_cache_headers,
)
from cladecanvas.api.models import SearchResult
from cladecanvas.api.search_ranking import (
    MAX_CANDIDATES,
    POSTGRES_TRIGRAM_THRESHOLD,
    expand_query_terms,
    extract_snippet,
    normalize_search_text,
    rank_search_row,
    sort_ranked_results,
)
from cladecanvas.schema import metadata_table, nodes

router = APIRouter(dependencies=[Depends(rate_limit_anonymous_reads)])


def _extract_snippet(text: str, query: str) -> str:
    return extract_snippet(text, expand_query_terms(query))


def _search_dialect(db: Session) -> str:
    bind = db.get_bind()
    return bind.dialect.name if bind is not None else ""


@router.get("", response_model=List[SearchResult])
def search_nodes(
    response: Response,
    q: str = Query(..., min_length=2, max_length=80),
    limit: int = Query(25, ge=1, le=MAX_SEARCH_LIMIT),
    offset: int = Query(0, ge=0, le=10000),
    db: Session = Depends(get_db),
):
    set_public_cache_headers(response)
    normalized_query = normalize_search_text(q)
    if len(normalized_query) < 2:
        raise HTTPException(
            status_code=422,
            detail="Search query must contain at least 2 non-whitespace characters.",
        )

    def load_search_results():
        return _search_nodes(normalized_query, limit, offset, db)

    return hot_read_cache.get_or_set(
        ("search", normalized_query.casefold(), limit, offset),
        load_search_results,
    )


def _search_nodes(q: str, limit: int, offset: int, db: Session) -> list[SearchResult]:
    apply_statement_timeout(db)
    query_terms = expand_query_terms(q)
    use_postgres_similarity = _search_dialect(db) == "postgresql"
    c = metadata_table.c
    n = nodes.c

    text_columns = (
        c.common_name,
        n.display_name,
        n.name,
        c.description,
        c.full_description,
    )

    filters = []
    prefix_filters = []
    for term in query_terms:
        contains_pattern = f"%{term}%"
        prefix_pattern = f"{term}%"
        term_prefix_filters = [
            column.ilike(prefix_pattern)
            for column in (c.common_name, n.display_name, n.name)
        ]
        filters.extend(column.ilike(contains_pattern) for column in text_columns)
        prefix_filters.extend(term_prefix_filters)
        filters.extend(term_prefix_filters)
        if use_postgres_similarity:
            filters.extend(
                func.similarity(func.coalesce(column, literal("")), term) >= POSTGRES_TRIGRAM_THRESHOLD
                for column in (c.common_name, n.display_name, n.name)
            )

    coarse_rank = case(
        (func.lower(c.common_name).in_(query_terms), 1),
        (or_(func.lower(n.display_name).in_(query_terms), func.lower(n.name).in_(query_terms)), 2),
        (or_(*prefix_filters), 3),
        else_=4,
    )

    stmt = (
        select(
            c.node_id,
            c.ott_id,
            c.common_name,
            n.display_name,
            n.name,
            c.description,
            c.full_description,
            c.image_url,
            c.wiki_page_url,
            c.enriched_score,
            c.source_label,
            c.enriched_at,
            c.provenance_confidence,
        )
        .select_from(metadata_table.join(nodes, c.node_id == n.node_id))
        .where(or_(*filters))
        .order_by(coarse_rank, c.node_id)
        .limit(max(MAX_CANDIDATES, offset + limit))
    )

    rows = db.execute(stmt).mappings().fetchall()
    ranked = []
    for row in rows:
        result = rank_search_row(row, q)
        if result:
            ranked.append((result, row))

    results = []
    row_by_id = {result.node_id: row for result, row in ranked}
    for result in sort_ranked_results([result for result, _ in ranked])[offset:offset + limit]:
        row = row_by_id[result.node_id]
        payload = {
            **result.__dict__,
            "source_label": row.get("source_label"),
            "enriched_at": row.get("enriched_at"),
            "provenance_confidence": row.get("provenance_confidence"),
        }
        results.append(SearchResult(**payload))
    return results
