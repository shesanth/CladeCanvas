import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.api


def test_dev_sqlite_read_only_routes_boot():
    from cladecanvas.api.main import app
    from cladecanvas.db import profile

    assert profile.name == "dev-sqlite"

    client = TestClient(app)

    root = client.get("/tree/root")
    assert root.status_code == 200
    assert root.json()["node_id"] == "ott691846"

    node = client.get("/node/ott683263")
    assert node.status_code == 200
    assert node.json()["name"] == "Eutheria"

    search = client.get("/search?q=Eutheria")
    assert search.status_code == 200
    assert search.json()[0]["node_id"] == "ott683263"


def test_dev_sqlite_database_is_read_only():
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    from cladecanvas.db import Session

    with Session() as session:
        with pytest.raises(OperationalError, match="readonly|read-only|attempt to write"):
            session.execute(
                text(
                    "INSERT INTO nodes (node_id, name) "
                    "VALUES ('ott999999999', 'Should Not Persist')"
                )
            )


def test_dev_sqlite_write_scripts_fail_clearly():
    import runpy

    from scripts import alias_mrca_nodes, discover_mrca_names, populate_db, run_workers

    with pytest.raises(RuntimeError, match="database population/enrichment.*dev-sqlite"):
        populate_db.main()

    with pytest.raises(RuntimeError, match="background enrichment workers.*dev-sqlite"):
        run_workers.main()

    with pytest.raises(RuntimeError, match="MRCA alias discovery.*dev-sqlite"):
        alias_mrca_nodes.find_aliases()

    with pytest.raises(RuntimeError, match="MRCA alias writes.*dev-sqlite"):
        discover_mrca_names.write_aliases([("mrcaott1ott2", "Example")])

    with pytest.raises(RuntimeError, match="metadata repair.*dev-sqlite"):
        runpy.run_module("scripts.fix_wrong_metadata", run_name="__main__")
