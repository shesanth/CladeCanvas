import re
import pytest


# ── MRCA node_id regex parsing ───────────────────────────────────────────────

MRCA_RE = re.compile(r"^mrcaott(\d+)ott(\d+)$")


class TestMrcaRegex:
    """Test the regex used in discover_mrca_names.py phase3 to parse MRCA node IDs."""

    def test_valid_mrca(self):
        m = MRCA_RE.match("mrcaott42ott150")
        assert m is not None
        assert int(m.group(1)) == 42
        assert int(m.group(2)) == 150

    def test_large_ott_ids(self):
        m = MRCA_RE.match("mrcaott83926ott3607676")
        assert m is not None
        assert int(m.group(1)) == 83926
        assert int(m.group(2)) == 3607676

    def test_zero_ott_ids(self):
        m = MRCA_RE.match("mrcaott0ott0")
        assert m is not None

    def test_rejects_taxon_node(self):
        assert MRCA_RE.match("ott123") is None

    def test_rejects_non_numeric(self):
        assert MRCA_RE.match("mrcaottXottY") is None

    def test_rejects_empty(self):
        assert MRCA_RE.match("") is None

    def test_rejects_partial(self):
        assert MRCA_RE.match("mrcaott42") is None

    def test_rejects_extra_suffix(self):
        assert MRCA_RE.match("mrcaott42ott150ott999") is None


# ── write_aliases dry-run behavior ───────────────────────────────────────────

class TestWriteAliases:
    def test_empty_aliases_no_op(self, capsys):
        """Empty alias list should print message and return."""
        from scripts.discover_mrca_names import write_aliases
        write_aliases([], dry_run=False)
        captured = capsys.readouterr()
        assert "No aliases" in captured.out

    def test_dry_run_prints_preview(self, capsys):
        """Dry run should print aliases without writing to DB."""
        from scripts.discover_mrca_names import write_aliases
        aliases = [
            ("mrcaott42ott150", "Planulozoa"),
            ("mrcaott42ott49", "Nephrozoa"),
        ]
        write_aliases(aliases, dry_run=True)
        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out
        assert "Planulozoa" in captured.out
        assert "Nephrozoa" in captured.out
        assert "2 aliases" in captured.out

    def test_dry_run_truncates_long_list(self, capsys):
        """Dry run with >20 aliases should show truncation message."""
        from scripts.discover_mrca_names import write_aliases
        aliases = [(f"mrcaott{i}ott{i+1}", f"Clade{i}") for i in range(25)]
        write_aliases(aliases, dry_run=True)
        captured = capsys.readouterr()
        assert "5 more" in captured.out
