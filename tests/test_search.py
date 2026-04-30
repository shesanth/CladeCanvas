import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cladecanvas.api.routes.search import _extract_snippet
from cladecanvas.api.routes.search import _normalize_query_or_422
from cladecanvas.api.routes.search import _search_nodes
from cladecanvas.api.search_ranking import rank_search_row, sort_ranked_results
from cladecanvas.schema import metadata, metadata_table, nodes


class TestExtractSnippet:
    def test_exact_match_short_text(self):
        text = "The domestic cat is a small mammal"
        assert _extract_snippet(text, "cat") == text

    def test_case_insensitive(self):
        text = "The domestic Cat is a small mammal"
        result = _extract_snippet(text, "cat")
        assert "Cat" in result

    def test_ellipsis_on_long_text(self):
        padding = "x" * 200
        text = f"{padding}TARGET{padding}"
        result = _extract_snippet(text, "TARGET")
        assert result.startswith("...")
        assert result.endswith("...")
        assert "TARGET" in result

    def test_no_leading_ellipsis_near_start(self):
        text = "cat " + "x" * 200
        result = _extract_snippet(text, "cat")
        assert not result.startswith("...")
        assert result.endswith("...")

    def test_no_trailing_ellipsis_near_end(self):
        text = "x" * 200 + " cat"
        result = _extract_snippet(text, "cat")
        assert result.startswith("...")
        assert not result.endswith("...")

    def test_empty_text(self):
        assert _extract_snippet("", "cat") == ""

    def test_no_match(self):
        assert _extract_snippet("dogs only here", "cat") == ""

    def test_special_regex_chars(self):
        text = "price is $100.00 (USD)"
        result = _extract_snippet(text, "$100.00")
        assert "$100.00" in result


class TestSearchRanking:
    def _row(
        self,
        node_id,
        common_name=None,
        display_name=None,
        name=None,
        description=None,
        full_description=None,
        enriched_score=0.0,
    ):
        return {
            "node_id": node_id,
            "ott_id": None,
            "common_name": common_name,
            "display_name": display_name,
            "name": name,
            "description": description,
            "full_description": full_description,
            "image_url": None,
            "wiki_page_url": None,
            "enriched_score": enriched_score,
        }

    def test_exact_common_name_wins_golden_query(self):
        rows = [
            self._row("2", display_name="cat", name="Felis"),
            self._row("1", common_name="cat", description="A small feline."),
            self._row("3", common_name="catfish", description="A ray-finned fish."),
        ]
        ranked = sort_ranked_results([rank_search_row(row, "cat") for row in rows])

        assert [result.node_id for result in ranked] == ["1", "2", "3"]
        assert ranked[0].match_type == "exact_common_name"
        assert ranked[0].score_breakdown["base"] == 1000.0

    def test_display_name_alias_beats_prefix(self):
        rows = [
            self._row("prefix", common_name="arachnid hunters"),
            self._row("alias", display_name="Arachnida", name="mrcaott1ott2"),
        ]
        ranked = sort_ranked_results([rank_search_row(row, "arachnida") for row in rows])

        assert [result.node_id for result in ranked] == ["alias", "prefix"]
        assert ranked[0].match_type == "display_name_alias"
        assert ranked[0].match_field == "display_name"

    def test_prefix_beats_description(self):
        rows = [
            self._row("description", description="A dolphin-like vertebrate."),
            self._row("prefix", common_name="dolphinfish"),
        ]
        ranked = sort_ranked_results([rank_search_row(row, "dolphin") for row in rows])

        assert [result.node_id for result in ranked] == ["prefix", "description"]
        assert ranked[0].match_type == "prefix"

    def test_description_beats_full_description(self):
        rows = [
            self._row("full", full_description="A long article about bats and echolocation."),
            self._row("short", description="A bat-like mammal."),
        ]
        ranked = sort_ranked_results([rank_search_row(row, "bat") for row in rows])

        assert [result.node_id for result in ranked] == ["short", "full"]
        assert ranked[0].match_type == "description"

    def test_synonym_support(self):
        result = rank_search_row(
            self._row("human", common_name="Homo sapiens", description="A primate."),
            "human",
        )

        assert result is not None
        assert result.match_type == "prefix"
        assert result.score_breakdown["matched_term"] == "homo sapiens"
        assert result.score_breakdown["synonym_boost"] > 0

    def test_typo_tolerance(self):
        result = rank_search_row(
            self._row("dolphin", common_name="dolphin"),
            "dolpin",
        )

        assert result is not None
        assert result.match_type == "typo"
        assert result.score_breakdown["similarity_boost"] > 0

    def test_no_match_returns_none(self):
        assert rank_search_row(self._row("cat", common_name="Cat"), "otter") is None


class TestSearchRoute:
    def _sqlite_session(self):
        engine = create_engine("sqlite:///:memory:")
        metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        session.execute(
            nodes.insert(),
            [
                {
                    "node_id": "cat",
                    "ott_id": 1,
                    "name": "Felis catus",
                    "parent_node_id": None,
                    "rank": "species",
                    "child_count": 0,
                    "has_metadata": 1,
                    "num_tips": 1,
                    "display_name": "Felis catus",
                },
                {
                    "node_id": "dog",
                    "ott_id": 2,
                    "name": "Canis lupus familiaris",
                    "parent_node_id": None,
                    "rank": "species",
                    "child_count": 0,
                    "has_metadata": 1,
                    "num_tips": 1,
                    "display_name": "Canis lupus familiaris",
                },
            ],
        )
        session.execute(
            metadata_table.insert(),
            [
                {
                    "node_id": "cat",
                    "ott_id": 1,
                    "common_name": "Cat",
                    "description": "A small domesticated feline.",
                    "full_description": "Cats are small carnivorous mammals.",
                    "image_url": None,
                    "wiki_page_url": None,
                    "enriched_score": 0.5,
                },
                {
                    "node_id": "dog",
                    "ott_id": 2,
                    "common_name": "Dog",
                    "description": "A friendly canine.",
                    "full_description": "Dogs are loyal mammals.",
                    "image_url": None,
                    "wiki_page_url": None,
                    "enriched_score": 0.4,
                },
            ],
        )
        session.commit()
        return session

    def test_sqlite_search_uses_like_candidates_without_similarity(self):
        session = self._sqlite_session()
        try:
            results = _search_nodes("cat", 25, 0, session)
        finally:
            session.close()

        assert [result.node_id for result in results] == ["cat"]
        assert results[0].match_type == "exact_common_name"

    def test_query_is_stripped_before_searching(self):
        session = self._sqlite_session()
        try:
            results = _search_nodes(_normalize_query_or_422("  cat  "), 25, 0, session)
        finally:
            session.close()

        assert [result.node_id for result in results] == ["cat"]

    def test_whitespace_query_returns_clear_422(self):
        session = self._sqlite_session()
        try:
            with pytest.raises(HTTPException) as exc_info:
                _normalize_query_or_422("  ")
        finally:
            session.close()

        assert exc_info.value.status_code == 422
        assert "non-whitespace" in exc_info.value.detail
