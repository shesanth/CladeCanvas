import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Mapping


SEARCH_LIMIT = 25
SNIPPET_RADIUS = 80

MAX_CANDIDATES = 200
TYPO_SIMILARITY_THRESHOLD = 0.82
POSTGRES_TRIGRAM_THRESHOLD = 0.22

MATCH_SCORES = {
    "exact_common_name": 1000.0,
    "display_name_alias": 900.0,
    "prefix": 760.0,
    "description": 520.0,
    "full_description": 440.0,
    "typo": 360.0,
}

FIELD_WEIGHTS = {
    "common_name": 90.0,
    "display_name": 70.0,
    "name": 60.0,
    "description": 30.0,
    "full_description": 20.0,
}

SYNONYM_BOOST = 30.0
ENRICHED_SCORE_WEIGHT = 12.0
PREFIX_BONUS = 20.0

QUERY_SYNONYMS = {
    "human": ("homo sapiens", "humans", "person", "people"),
    "humans": ("homo sapiens", "human", "person", "people"),
    "person": ("homo sapiens", "human", "humans", "people"),
    "cat": ("cats", "feline", "felis catus", "felidae"),
    "cats": ("cat", "feline", "felis catus", "felidae"),
    "dog": ("dogs", "canine", "canis lupus familiaris", "canidae"),
    "dogs": ("dog", "canine", "canis lupus familiaris", "canidae"),
    "spider": ("spiders", "arachnid", "arachnida"),
    "spiders": ("spider", "arachnid", "arachnida"),
    "bird": ("birds", "aves", "avian"),
    "birds": ("bird", "aves", "avian"),
    "snake": ("snakes", "serpent", "serpentes"),
    "snakes": ("snake", "serpent", "serpentes"),
}


@dataclass(frozen=True)
class RankedSearchResult:
    node_id: str
    ott_id: int | None
    common_name: str | None
    display_name: str | None
    description: str | None
    image_url: str | None
    wiki_page_url: str | None
    enriched_score: float | None
    match_field: str
    match_snippet: str
    match_type: str
    score: float
    score_breakdown: dict[str, float | str]


def normalize_search_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def expand_query_terms(query: str) -> list[str]:
    normalized = normalize_search_text(query)
    terms = [normalized]
    for synonym in QUERY_SYNONYMS.get(normalized, ()):
        if synonym not in terms:
            terms.append(synonym)
    return terms


def extract_snippet(text: str | None, query_terms: list[str]) -> str:
    if not text:
        return ""

    best_match: re.Match[str] | None = None
    for term in query_terms:
        match = re.search(re.escape(term), text, re.IGNORECASE)
        if match and (best_match is None or match.start() < best_match.start()):
            best_match = match

    if not best_match:
        return ""

    start = max(0, best_match.start() - SNIPPET_RADIUS)
    end = min(len(text), best_match.end() + SNIPPET_RADIUS)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet += "..."
    return snippet


def rank_search_row(row: Mapping[str, Any], query: str) -> RankedSearchResult | None:
    query_terms = expand_query_terms(query)
    primary_query = query_terms[0]

    fields = {
        "common_name": row.get("common_name"),
        "display_name": row.get("display_name"),
        "name": row.get("name"),
        "description": row.get("description"),
        "full_description": row.get("full_description"),
    }
    normalized_fields = {
        field: normalize_search_text(value)
        for field, value in fields.items()
    }

    match_type, match_field, matched_term, similarity = _best_match(
        normalized_fields, query_terms, primary_query
    )
    if not match_type or not match_field:
        return None

    base = MATCH_SCORES[match_type]
    field_boost = FIELD_WEIGHTS[match_field]
    synonym_boost = SYNONYM_BOOST if matched_term != primary_query else 0.0
    enriched_boost = float(row.get("enriched_score") or 0.0) * ENRICHED_SCORE_WEIGHT
    prefix_boost = PREFIX_BONUS if match_type == "prefix" else 0.0
    similarity_boost = round(similarity * 50.0, 3)
    score = base + field_boost + synonym_boost + enriched_boost + prefix_boost + similarity_boost

    snippet_source = fields.get(match_field)
    if match_field in ("description", "full_description"):
        snippet = extract_snippet(snippet_source, query_terms) or (snippet_source or "")
    else:
        snippet = snippet_source or ""

    return RankedSearchResult(
        node_id=row["node_id"],
        ott_id=row.get("ott_id"),
        common_name=row.get("common_name"),
        display_name=row.get("display_name"),
        description=row.get("description"),
        image_url=row.get("image_url"),
        wiki_page_url=row.get("wiki_page_url"),
        enriched_score=row.get("enriched_score"),
        match_field=match_field,
        match_snippet=snippet,
        match_type=match_type,
        score=round(score, 3),
        score_breakdown={
            "base": base,
            "field_boost": field_boost,
            "synonym_boost": synonym_boost,
            "enriched_boost": round(enriched_boost, 3),
            "prefix_boost": prefix_boost,
            "similarity_boost": similarity_boost,
            "matched_term": matched_term,
        },
    )


def sort_ranked_results(results: list[RankedSearchResult]) -> list[RankedSearchResult]:
    return sorted(results, key=lambda result: (-result.score, result.node_id))


def _best_match(
    fields: Mapping[str, str],
    query_terms: list[str],
    primary_query: str,
) -> tuple[str | None, str | None, str, float]:
    if fields["common_name"] == primary_query:
        return "exact_common_name", "common_name", primary_query, 1.0

    for field in ("display_name", "name"):
        for term in query_terms:
            if fields[field] == term:
                return "display_name_alias", field, term, 1.0

    for field in ("common_name", "display_name", "name"):
        for term in query_terms:
            if fields[field].startswith(term):
                return "prefix", field, term, 1.0

    for field in ("description", "full_description"):
        for term in query_terms:
            if term in fields[field]:
                return "description" if field == "description" else "full_description", field, term, 1.0

    typo_match = _best_typo_match(fields, primary_query)
    if typo_match:
        return typo_match

    return None, None, primary_query, 0.0


def _best_typo_match(
    fields: Mapping[str, str],
    query: str,
) -> tuple[str, str, str, float] | None:
    best: tuple[str, str, str, float] | None = None
    for field in ("common_name", "display_name", "name"):
        value = fields[field]
        if not value:
            continue
        candidates = [value, *value.split()]
        for candidate in candidates:
            similarity = SequenceMatcher(None, query, candidate).ratio()
            if similarity >= TYPO_SIMILARITY_THRESHOLD and (
                best is None or similarity > best[3]
            ):
                best = ("typo", field, candidate, similarity)
    return best
