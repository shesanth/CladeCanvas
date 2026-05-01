from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import or_, select
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
    normalized_query = _normalize_query_or_422(q)

    def load_search_results():
        return _search_nodes(normalized_query, limit, offset, db)

    return hot_read_cache.get_or_set(
        ("search", normalized_query.casefold(), limit, offset),
        load_search_results,
    )


def _normalize_query_or_422(q: str) -> str:
    normalized_query = normalize_search_text(q)
    if len(normalized_query) < 2:
        raise HTTPException(
            status_code=422,
            detail="Search query must contain at least 2 non-whitespace characters.",
        )
    return normalized_query


def _search_nodes(q: str, limit: int, offset: int, db: Session) -> list[SearchResult]:
    apply_statement_timeout(db)
    query_terms = expand_query_terms(q)
    use_postgres_similarity = _search_dialect(db) == "postgresql"
    c = metadata_table.c
    n = nodes.c

    metadata_prefix_filters = []
    node_prefix_filters = []
    metadata_fuzzy_filters = []
    node_fuzzy_filters = []
    for term in query_terms:
        prefix_pattern = f"{term}%"
        metadata_prefix_filters.append(c.common_name.ilike(prefix_pattern))
        node_prefix_filters.extend([
            n.display_name.ilike(prefix_pattern),
            n.name.ilike(prefix_pattern),
        ])
        if use_postgres_similarity:
            metadata_fuzzy_filters.append(c.common_name.op("%")(term))
            node_fuzzy_filters.extend([
                n.display_name.op("%")(term),
                n.name.op("%")(term),
            ])
        else:
            contains_pattern = f"%{term}%"
            metadata_fuzzy_filters.append(c.common_name.ilike(contains_pattern))
            node_fuzzy_filters.extend([
                n.display_name.ilike(contains_pattern),
                n.name.ilike(contains_pattern),
            ])

    base_select = select(
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
    ).select_from(metadata_table.join(nodes, c.node_id == n.node_id))

    candidate_limit = max(MAX_CANDIDATES, offset + limit)
    rows_by_id = {}

    def load_candidates(filter_groups):
        for filters in filter_groups:
            if not filters:
                continue
            rows = db.execute(
                base_select
                .where(or_(*filters))
                .limit(candidate_limit)
            ).mappings().fetchall()
            rows_by_id.update({row["node_id"]: row for row in rows})

    load_candidates((metadata_prefix_filters, node_prefix_filters))

    ranked = []
    for row in rows_by_id.values():
        result = rank_search_row(row, q)
        if result:
            ranked.append((result, row))

    if not ranked:
        load_candidates((metadata_fuzzy_filters, node_fuzzy_filters))
        for row in rows_by_id.values():
            result = rank_search_row(row, q)
            if result:
                ranked.append((result, row))

    if not ranked:
        existing_ids = set()
        description_filters = []
        for term in query_terms:
            contains_pattern = f"%{term}%"
            if len(term) >= 4:
                description_filters.append(c.description.ilike(contains_pattern))
            if len(term) >= 6:
                description_filters.append(c.full_description.ilike(contains_pattern))

        if description_filters:
            description_stmt = (
                base_select
                .where(or_(*description_filters))
                .limit(candidate_limit)
            )
            for row in db.execute(description_stmt).mappings().fetchall():
                if row["node_id"] in existing_ids:
                    continue
                result = rank_search_row(row, q)
                if result:
                    ranked.append((result, row))
                    existing_ids.add(result.node_id)

    if not ranked:
        return []

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
