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
