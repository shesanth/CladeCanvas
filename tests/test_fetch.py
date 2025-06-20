import csv
import importlib
from cladecanvas import fetch_otol

def test_download_and_flatten(tmp_path, monkeypatch):
    # Setup
    dummy_newick = '(A_ott1,B_ott2)Root_ott3;'
    class DummyResp:
        def __init__(self, newick):
            self.response_dict = {'newick': newick}

    importlib.reload(fetch_otol)

    monkeypatch.setattr(fetch_otol, 'DATA_DIR', str(tmp_path))
    raw_path = tmp_path / f"{fetch_otol.TAXON.lower()}.newick"
    csv_path = tmp_path / f"{fetch_otol.TAXON.lower()}_nodes.csv"
    monkeypatch.setattr(fetch_otol, 'RAW_PATH', str(raw_path))
    monkeypatch.setattr(fetch_otol, 'CSV_PATH', str(csv_path))

    monkeypatch.setattr(fetch_otol.OT, 'taxon_subtree', lambda ott_id: DummyResp(dummy_newick))

    # Run
    fetch_otol.download_taxonomy()
    fetch_otol.flatten_newick()

    # Assert
    assert raw_path.exists(), "Raw Newick file was not created"
    assert csv_path.exists(), "CSV file was not created"

    # Validate
    rows = list(csv.DictReader(open(csv_path)))
    expected = [
        {'ott_id': '3', 'name': 'Root', 'parent_ott_id': ''},
        {'ott_id': '1', 'name': 'A', 'parent_ott_id': '3'},
        {'ott_id': '2', 'name': 'B', 'parent_ott_id': '3'},
    ]
    for exp in expected:
        assert exp in rows, f"Expected row {exp} not found in CSV"