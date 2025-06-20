import os
import pytest
from fastapi.testclient import TestClient
from cladecanvas.api.main import app

skip_on_ci = os.getenv("SKIP_API_TESTS") == "1"

client = TestClient(app)

@pytest.mark.skipif(skip_on_ci, reason="Skipping API tests on CI (no DB)")
def test_root_node():
    response = client.get("/tree/root")
    assert response.status_code == 200
    data = response.json()
    assert "ott_id" in data
    assert data.get("parent_ott_id") is None  # root has no parent

@pytest.mark.skipif(skip_on_ci, reason="Skipping API tests on CI (no DB)")
def test_children():
    response = client.get("/tree/children/691846")  # Metazoa
    assert response.status_code == 200
    assert isinstance(response.json(), list)

@pytest.mark.skipif(skip_on_ci, reason="Skipping API tests on CI (no DB)")
def test_node_metadata():
    response = client.get("/node/683263") # Eutheria
    if response.status_code == 404:
        pytest.skip("OTT ID not found in test DB")
    assert response.status_code == 200
    assert "common_name" in response.json()

@pytest.mark.skipif(skip_on_ci, reason="Skipping API tests on CI (no DB)")
def test_lineage():
    response = client.get("/tree/lineage/683263")
    assert response.status_code == 200
    lineage = response.json()["lineage"]
    assert isinstance(lineage, list)
    assert len(lineage) >= 1

@pytest.mark.skipif(skip_on_ci, reason="Skipping API tests on CI (no DB)")
def test_search():
    response = client.get("/search?q=Eutheria")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert "ott_id" in response.json()[0]