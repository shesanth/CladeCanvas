import pytest
from unittest.mock import patch, MagicMock
from cladecanvas.enrich import clean_taxon_name, fetch_wikipedia_extract, fetch_wikidata


# ── clean_taxon_name ─────────────────────────────────────────────────────────

class TestCleanTaxonName:
    def test_strips_parenthetical(self):
        assert clean_taxon_name("Homo sapiens (fossil)") == "Homo sapiens"

    def test_strips_nested_parenthetical(self):
        assert clean_taxon_name("Aus (genus) bus") == "Aus bus"

    def test_strips_sp_code(self):
        assert clean_taxon_name("Aus sp. BX-103") == "Aus"

    def test_bare_sp_only_strips_when_adjacent_to_word(self):
        # \bsp\.\b requires word boundary after period — only fires when a
        # word char immediately follows the dot (e.g. "sp.end")
        assert clean_taxon_name("Aus sp.end") == "Aus end"
        # With a space or at end of string, the bare sp. regex does NOT match
        assert clean_taxon_name("Aus sp.") == "Aus sp."
        assert clean_taxon_name("Aus sp. something") == "Aus sp. something"

    def test_collapses_whitespace(self):
        assert clean_taxon_name("  Homo   sapiens  ") == "Homo sapiens"

    def test_combined_parenthetical_and_sp(self):
        assert clean_taxon_name("Aus (genus) sp. XYZ") == "Aus"

    def test_non_string_int(self):
        assert clean_taxon_name(12345) == "12345"

    def test_non_string_none(self):
        assert clean_taxon_name(None) == "None"

    def test_empty_string(self):
        assert clean_taxon_name("") == ""

    def test_no_change_needed(self):
        assert clean_taxon_name("Bilateria") == "Bilateria"

    def test_multiple_parentheticals(self):
        assert clean_taxon_name("Aus (a) bus (b)") == "Aus bus"

    def test_sp_with_colon_code(self):
        assert clean_taxon_name("Aus sp. BOLD:AAB1234") == "Aus"


# ── fetch_wikipedia_extract ──────────────────────────────────────────────────

class TestFetchWikipediaExtract:
    @patch("cladecanvas.enrich.requests.get")
    def test_happy_path(self, mock_get):
        """Full pipeline: Wikidata sitelink -> Wikipedia extract."""
        wikidata_resp = MagicMock()
        wikidata_resp.json.return_value = {
            "entities": {
                "Q5173": {
                    "sitelinks": {
                        "enwiki": {"title": "Bilateria"}
                    }
                }
            }
        }
        wiki_resp = MagicMock()
        wiki_resp.json.return_value = {
            "query": {
                "pages": [{"extract": "<p>Bilateria are animals.</p>"}]
            }
        }
        mock_get.side_effect = [wikidata_resp, wiki_resp]

        text, url = fetch_wikipedia_extract("Q5173")
        assert text is not None
        assert "Bilateria" in text
        assert url == "https://en.wikipedia.org/wiki/Bilateria"

    @patch("cladecanvas.enrich.requests.get")
    def test_no_enwiki_sitelink(self, mock_get):
        """No English Wikipedia article -> (None, None)."""
        resp = MagicMock()
        resp.json.return_value = {
            "entities": {
                "Q999": {"sitelinks": {"dewiki": {"title": "Etwas"}}}
            }
        }
        mock_get.return_value = resp

        text, url = fetch_wikipedia_extract("Q999")
        assert text is None
        assert url is None

    @patch("cladecanvas.enrich.requests.get")
    def test_wikipedia_no_extract(self, mock_get):
        """Wikipedia page exists but has no extract field."""
        wikidata_resp = MagicMock()
        wikidata_resp.json.return_value = {
            "entities": {
                "Q123": {
                    "sitelinks": {"enwiki": {"title": "SomeTaxon"}}
                }
            }
        }
        wiki_resp = MagicMock()
        wiki_resp.json.return_value = {
            "query": {"pages": [{"title": "SomeTaxon"}]}
        }
        mock_get.side_effect = [wikidata_resp, wiki_resp]

        text, url = fetch_wikipedia_extract("Q123")
        assert text is None
        assert url == "https://en.wikipedia.org/wiki/SomeTaxon"


# ── fetch_wikidata ───────────────────────────────────────────────────────────

class TestFetchWikidata:
    @patch("cladecanvas.enrich.fetch_wikipedia_extract", return_value=(None, None))
    @patch("cladecanvas.enrich.requests.get")
    def test_empty_input(self, mock_get, mock_wiki):
        """Empty node list should return empty results."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": {"bindings": []}}
        mock_get.return_value = mock_resp

        results = fetch_wikidata([])
        assert results == []

    @patch("cladecanvas.enrich.fetch_wikipedia_extract")
    @patch("cladecanvas.enrich.requests.get")
    def test_p9157_hit(self, mock_get, mock_wiki):
        """P9157 SPARQL match returns enriched record."""
        mock_wiki.return_value = ("<p>Description</p>", "https://en.wikipedia.org/wiki/Bilateria")
        sparql_resp = MagicMock()
        sparql_resp.json.return_value = {
            "results": {
                "bindings": [{
                    "ott": {"value": "117569"},
                    "item": {"value": "http://www.wikidata.org/entity/Q5173"},
                    "itemLabel": {"value": "Bilateria"},
                    "desc": {"value": "large clade of animals"},
                    "image": {"value": "http://example.com/img.jpg"},
                }]
            }
        }
        mock_get.return_value = sparql_resp

        nodes = [{"ott_id": 117569, "name": "Bilateria", "node_id": "ott117569"}]
        results = fetch_wikidata(nodes)

        assert len(results) == 1
        assert results[0]["ott_id"] == 117569
        assert results[0]["wikidata_q"] == "Q5173"
        assert results[0]["common_name"] == "Bilateria"
        assert results[0]["enriched_score"] == 1.0

    @patch("cladecanvas.enrich.fetch_wikipedia_extract")
    @patch("cladecanvas.enrich.requests.get")
    def test_enriched_score_zero_when_no_desc_no_image(self, mock_get, mock_wiki):
        """Score should be 0.0 when no full_description and no image."""
        mock_wiki.return_value = (None, None)
        sparql_resp = MagicMock()
        sparql_resp.json.return_value = {
            "results": {
                "bindings": [{
                    "ott": {"value": "999"},
                    "item": {"value": "http://www.wikidata.org/entity/Q999"},
                    "itemLabel": {"value": "Obscurata"},
                }]
            }
        }
        mock_get.return_value = sparql_resp

        results = fetch_wikidata([{"ott_id": 999, "name": "Obscurata", "node_id": "ott999"}])
        assert len(results) == 1
        assert results[0]["enriched_score"] == 0.0

    @patch("cladecanvas.enrich.fetch_wikipedia_extract")
    @patch("cladecanvas.enrich.requests.get")
    def test_fallback_by_name(self, mock_get, mock_wiki):
        """When P9157 misses, fallback queries by taxon name (P225)."""
        mock_wiki.return_value = (None, "https://en.wikipedia.org/wiki/Rara")

        # First call: P9157 SPARQL returns nothing
        sparql_empty = MagicMock()
        sparql_empty.json.return_value = {"results": {"bindings": []}}

        # Second call: P225 fallback returns a match
        sparql_fallback = MagicMock()
        sparql_fallback.json.return_value = {
            "results": {
                "bindings": [{
                    "item": {"value": "http://www.wikidata.org/entity/Q888"},
                    "itemLabel": {"value": "Rara"},
                }]
            }
        }
        mock_get.side_effect = [sparql_empty, sparql_fallback]

        results = fetch_wikidata([{"ott_id": 888, "name": "Rara", "node_id": "ott888"}])
        assert len(results) == 1
        assert results[0]["wikidata_q"] == "Q888"

    @patch("cladecanvas.enrich.fetch_wikipedia_extract")
    @patch("cladecanvas.enrich.requests.get")
    def test_sp_name_skips_fallback(self, mock_get, mock_wiki):
        """Nodes with 'sp.' in name should NOT fallback to parent clade."""
        mock_wiki.return_value = (None, None)

        # P9157 returns nothing (no OTT match for this specimen)
        sparql_empty = MagicMock()
        sparql_empty.json.return_value = {"results": {"bindings": []}}
        mock_get.return_value = sparql_empty

        results = fetch_wikidata([
            {"ott_id": 77777, "name": "Rodentia sp. BX-103", "node_id": "ott77777"}
        ])
        assert len(results) == 0
        # Should only have called SPARQL once (P9157), NOT the P225 fallback
        assert mock_get.call_count == 1
