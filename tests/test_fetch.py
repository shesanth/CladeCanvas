from src.fetch_otol import ensure_data_dir, fetch_newick, parse_newick_to_csv, NODE_CSV
import os, tempfile, shutil, importlib

def test_fetch_and_parse(tmp_path, monkeypatch):
    # point the module's DATA_DIR at a temp dir
    monkeypatch.setattr("src.fetch_otol.DATA_DIR", tmp_path)
    importlib.reload(importlib.import_module("src.fetch_otol"))

    ensure_data_dir()
    fetch_newick()
    parse_newick_to_csv()
    assert (tmp_path / "animalia_nodes.csv").exists()