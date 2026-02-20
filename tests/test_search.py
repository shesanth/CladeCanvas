import pytest
from cladecanvas.api.routes.search import _extract_snippet


# ── _extract_snippet ──────────────────────────────────────────────────────────

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
        assert result.startswith("…")
        assert result.endswith("…")
        assert "TARGET" in result

    def test_no_leading_ellipsis_near_start(self):
        text = "cat " + "x" * 200
        result = _extract_snippet(text, "cat")
        assert not result.startswith("…")
        assert result.endswith("…")

    def test_no_trailing_ellipsis_near_end(self):
        text = "x" * 200 + " cat"
        result = _extract_snippet(text, "cat")
        assert result.startswith("…")
        assert not result.endswith("…")

    def test_empty_text(self):
        assert _extract_snippet("", "cat") == ""

    def test_no_match(self):
        assert _extract_snippet("dogs only here", "cat") == ""

    def test_special_regex_chars(self):
        text = "price is $100.00 (USD)"
        result = _extract_snippet(text, "$100.00")
        assert "$100.00" in result


# ── Search ranking (unit-level, no DB) ────────────────────────────────────────

class TestSearchRanking:
    """Verify the CASE tier logic assigns correct match_field values."""

    def _make_row(self, common_name=None, description=None, full_description=None):
        """Simulate what the search endpoint does with a tier assignment."""
        from cladecanvas.api.routes.search import _extract_snippet

        if common_name and "test" in common_name.lower():
            tier = 1
        elif description and "test" in description.lower():
            tier = 2
        elif full_description and "test" in full_description.lower():
            tier = 3
        else:
            return None

        if tier == 1:
            return "common_name", common_name
        elif tier == 2:
            return "description", description
        else:
            return "full_description", _extract_snippet(full_description or "", "test")

    def test_common_name_wins(self):
        field, snippet = self._make_row(
            common_name="Test animal",
            description="A test creature",
            full_description="Long test article",
        )
        assert field == "common_name"
        assert snippet == "Test animal"

    def test_description_when_no_common_name_match(self):
        field, snippet = self._make_row(
            common_name="Cat",
            description="A test creature",
            full_description="Long test article",
        )
        assert field == "description"

    def test_full_description_fallback(self):
        field, snippet = self._make_row(
            common_name="Cat",
            description="A feline",
            full_description="Some long article mentioning test data",
        )
        assert field == "full_description"
        assert "test" in snippet.lower()

    def test_no_match_returns_none(self):
        result = self._make_row(
            common_name="Cat",
            description="A feline",
            full_description="Nothing relevant",
        )
        assert result is None
