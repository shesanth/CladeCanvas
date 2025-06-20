import pytest
from fastapi.testclient import TestClient

@pytest.mark.api
def test_root_node():
    from cladecanvas.api.main import app
    client = TestClient(app)
    response = client.get("/tree/root")
    assert response.status_code == 200
    data = response.json()
    assert "ott_id" in data
    assert data.get("parent_ott_id") is None  # root has no parent

@pytest.mark.api
def test_children():
    from cladecanvas.api.main import app
    client = TestClient(app)
    response = client.get("/tree/children/691846")  # Metazoa
    assert response.status_code == 200
    assert isinstance(response.json(), list)

@pytest.mark.api
def test_node_metadata():
    from cladecanvas.api.main import app
    client = TestClient(app)
    response = client.get("/node/683263") # Eutheria
    if response.status_code == 404:
        pytest.skip("OTT ID not found in test DB")
    assert response.status_code == 200
    assert "common_name" in response.json()

@pytest.mark.api
def test_lineage():
    from cladecanvas.api.main import app
    client = TestClient(app)
    response = client.get("/tree/lineage/683263")
    assert response.status_code == 200
    lineage = response.json()["lineage"]
    assert isinstance(lineage, list)
    assert len(lineage) >= 1

@pytest.mark.api
def test_search():
    from cladecanvas.api.main import app
    client = TestClient(app)
    response = client.get("/search?q=Eutheria")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert "ott_id" in response.json()[0]
