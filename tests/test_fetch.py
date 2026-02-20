import csv
import json
import importlib
from unittest.mock import patch
from cladecanvas import fetch_otol


def _make_arguson_tree():
    """Return a minimal arguson tree with 3 nodes."""
    return {
        "node_id": "ott3",
        "taxon": {"ott_id": 3, "name": "Root"},
        "num_tips": 2,
        "children": [
            {
                "node_id": "ott1",
                "taxon": {"ott_id": 1, "name": "A"},
                "num_tips": 1,
                "children": [],
            },
            {
                "node_id": "ott2",
                "taxon": {"ott_id": 2, "name": "B"},
                "num_tips": 1,
                "children": [],
            },
        ],
    }


def test_parse_arguson_flat():
    """_parse_arguson should flatten an arguson tree into rows."""
    importlib.reload(fetch_otol)
    tree = _make_arguson_tree()
    rows = []
    seen = set()
    frontier = []
    fetch_otol._parse_arguson(tree, None, rows, seen, frontier)

    assert len(rows) == 3
    ids = {r["node_id"] for r in rows}
    assert ids == {"ott1", "ott2", "ott3"}

    root = next(r for r in rows if r["node_id"] == "ott3")
    assert root["name"] == "Root"
    assert root["parent_node_id"] is None

    child_a = next(r for r in rows if r["node_id"] == "ott1")
    assert child_a["parent_node_id"] == "ott3"


def test_parse_arguson_truncated_frontier():
    """Truncated nodes (num_tips > 1, no children key) go to the frontier."""
    importlib.reload(fetch_otol)
    tree = {
        "node_id": "ott10",
        "taxon": {"ott_id": 10, "name": "BigClade"},
        "num_tips": 500,
        # no "children" key — indicates truncation
    }
    rows = []
    seen = set()
    frontier = []
    fetch_otol._parse_arguson(tree, None, rows, seen, frontier)

    assert len(rows) == 1
    assert frontier == ["ott10"]


def test_parse_arguson_synthetic_name():
    """Synthetic MRCA nodes without a taxon should use descendant_name_list."""
    importlib.reload(fetch_otol)
    tree = {
        "node_id": "mrcaott42ott150",
        "descendant_name_list": ["Bilateria", "Cnidaria"],
        "num_tips": 100,
        "children": [],
    }
    rows = []
    seen = set()
    frontier = []
    fetch_otol._parse_arguson(tree, "ott691846", rows, seen, frontier)

    assert len(rows) == 1
    assert rows[0]["name"] == "Bilateria + Cnidaria"
    assert rows[0]["ott_id"] is None
    assert rows[0]["parent_node_id"] == "ott691846"


def test_download_synth_writes_csv(tmp_path, monkeypatch):
    """download_synth_arguson should write a CSV via the arguson API."""
    importlib.reload(fetch_otol)

    monkeypatch.setattr(fetch_otol, "DATA_DIR", str(tmp_path))
    csv_path = str(tmp_path / "metazoa_nodes_synth.csv")
    monkeypatch.setattr(fetch_otol, "CSV_PATH", csv_path)

    tree = _make_arguson_tree()

    with patch.object(fetch_otol, "_arguson_subtree", return_value=tree):
        fetch_otol.download_synth_arguson()

    assert (tmp_path / "metazoa_nodes_synth.csv").exists()
    rows = list(csv.DictReader(open(csv_path)))
    assert len(rows) == 3
    names = {r["name"] for r in rows}
    assert names == {"Root", "A", "B"}


# ── Edge cases ───────────────────────────────────────────────────────────────

def test_parse_empty_node_id():
    """Node with empty node_id should be silently skipped."""
    importlib.reload(fetch_otol)
    tree = {"node_id": "", "taxon": {"ott_id": 1, "name": "Ghost"}, "children": []}
    rows, seen, frontier = [], set(), []
    fetch_otol._parse_arguson(tree, None, rows, seen, frontier)
    assert rows == []


def test_parse_deduplication():
    """A node already in 'seen' should not produce a second row."""
    importlib.reload(fetch_otol)
    tree = {
        "node_id": "ott5",
        "taxon": {"ott_id": 5, "name": "Dup"},
        "num_tips": 1,
        "children": [],
    }
    rows, frontier = [], []
    seen = {"ott5"}  # already seen
    fetch_otol._parse_arguson(tree, None, rows, seen, frontier)
    assert len(rows) == 0  # no new row added


def test_parse_synthetic_empty_descendant_list():
    """MRCA node with empty descendant_name_list falls back to node_id."""
    importlib.reload(fetch_otol)
    tree = {
        "node_id": "mrcaott1ott2",
        "descendant_name_list": [],
        "num_tips": 5,
        "children": [],
    }
    rows, seen, frontier = [], set(), []
    fetch_otol._parse_arguson(tree, None, rows, seen, frontier)
    assert rows[0]["name"] == "mrcaott1ott2"


def test_leaf_num_tips_one_not_in_frontier():
    """A leaf with num_tips=1 and no children key should NOT be in the frontier."""
    importlib.reload(fetch_otol)
    tree = {
        "node_id": "ott99",
        "taxon": {"ott_id": 99, "name": "Leaf"},
        "num_tips": 1,
    }
    rows, seen, frontier = [], set(), []
    fetch_otol._parse_arguson(tree, None, rows, seen, frontier)
    assert len(rows) == 1
    assert frontier == []


def test_leaf_num_tips_zero_not_in_frontier():
    """A node with num_tips=0 should NOT be in the frontier."""
    importlib.reload(fetch_otol)
    tree = {
        "node_id": "ott0",
        "taxon": {"ott_id": 0, "name": "Empty"},
        "num_tips": 0,
    }
    rows, seen, frontier = [], set(), []
    fetch_otol._parse_arguson(tree, None, rows, seen, frontier)
    assert frontier == []


def test_download_multi_wave(tmp_path, monkeypatch):
    """download_synth_arguson should expand truncated nodes in subsequent waves."""
    importlib.reload(fetch_otol)
    monkeypatch.setattr(fetch_otol, "DATA_DIR", str(tmp_path))
    csv_path = str(tmp_path / "metazoa_nodes_synth.csv")
    monkeypatch.setattr(fetch_otol, "CSV_PATH", csv_path)
    monkeypatch.setattr(fetch_otol, "OTT_ID", 100)  # root = ott100

    # Wave 1: root with a truncated child (no children key, num_tips > 1)
    wave1_tree = {
        "node_id": "ott100",
        "taxon": {"ott_id": 100, "name": "Root"},
        "num_tips": 10,
        "children": [
            {
                "node_id": "ott200",
                "taxon": {"ott_id": 200, "name": "Truncated"},
                "num_tips": 5,
                # no "children" key -> goes to frontier
            },
        ],
    }
    # Wave 2: expanding the truncated node
    wave2_tree = {
        "node_id": "ott200",
        "taxon": {"ott_id": 200, "name": "Truncated"},
        "num_tips": 5,
        "children": [
            {
                "node_id": "ott201",
                "taxon": {"ott_id": 201, "name": "Child1"},
                "num_tips": 1,
                "children": [],
            },
        ],
    }

    call_count = [0]

    def mock_subtree(node_id):
        call_count[0] += 1
        if node_id == "ott100":
            return wave1_tree
        elif node_id == "ott200":
            return wave2_tree
        return None

    with patch.object(fetch_otol, "_arguson_subtree", side_effect=mock_subtree):
        fetch_otol.download_synth_arguson()

    rows = list(csv.DictReader(open(csv_path)))
    names = {r["name"] for r in rows}
    assert "Root" in names
    assert "Child1" in names
    assert call_count[0] == 2  # two API calls: wave 1 + wave 2


def test_download_handles_none_subtree(tmp_path, monkeypatch):
    """download_synth_arguson should handle _arguson_subtree returning None."""
    importlib.reload(fetch_otol)
    monkeypatch.setattr(fetch_otol, "DATA_DIR", str(tmp_path))
    csv_path = str(tmp_path / "metazoa_nodes_synth.csv")
    monkeypatch.setattr(fetch_otol, "CSV_PATH", csv_path)

    with patch.object(fetch_otol, "_arguson_subtree", return_value=None):
        fetch_otol.download_synth_arguson()

    rows = list(csv.DictReader(open(csv_path)))
    assert len(rows) == 0  # no data, but CSV still created with headers
