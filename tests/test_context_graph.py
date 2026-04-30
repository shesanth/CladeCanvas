from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def test_context_graph_is_deterministic_and_compressed():
    from cladecanvas.api.deps import get_db
    from cladecanvas.api.main import app
    from cladecanvas.schema import metadata, nodes

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    rows = [
        {"node_id": "root", "name": "Root", "parent_node_id": None, "child_count": 4, "has_metadata": 0, "num_tips": 100},
        {"node_id": "branch", "name": "Branch", "parent_node_id": "root", "child_count": 4, "has_metadata": 0, "num_tips": 80},
        {"node_id": "root-sib-a", "name": "Root Sibling A", "parent_node_id": "root", "child_count": 0, "has_metadata": 0, "num_tips": 70},
        {"node_id": "root-sib-b", "name": "Root Sibling B", "parent_node_id": "root", "child_count": 0, "has_metadata": 0, "num_tips": 60},
        {"node_id": "root-sib-c", "name": "Root Sibling C", "parent_node_id": "root", "child_count": 0, "has_metadata": 0, "num_tips": 50},
        {"node_id": "focus", "name": "Focus", "parent_node_id": "branch", "child_count": 3, "has_metadata": 1, "num_tips": 40},
        {"node_id": "branch-sib-a", "name": "Branch Sibling A", "parent_node_id": "branch", "child_count": 0, "has_metadata": 0, "num_tips": 30},
        {"node_id": "branch-sib-b", "name": "Branch Sibling B", "parent_node_id": "branch", "child_count": 0, "has_metadata": 0, "num_tips": 20},
        {"node_id": "child-a", "name": "Child A", "parent_node_id": "focus", "child_count": 0, "has_metadata": 0, "num_tips": 9},
        {"node_id": "child-b", "name": "Child B", "parent_node_id": "focus", "child_count": 0, "has_metadata": 0, "num_tips": 8},
        {"node_id": "child-c", "name": "Child C", "parent_node_id": "focus", "child_count": 0, "has_metadata": 0, "num_tips": 7},
    ]

    with engine.begin() as conn:
        conn.execute(insert(nodes), rows)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.get("/tree/context/focus?sibling_limit=1&child_limit=2")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert [node["node_id"] for node in data["lineage"]] == ["root", "branch", "focus"]
    assert [node["node_id"] for node in data["nodes"] if node["kind"] == "sibling"] == [
        "root-sib-a",
        "branch-sib-a",
    ]
    assert [node["node_id"] for node in data["nodes"] if node["kind"] == "child"] == [
        "child-a",
        "child-b",
    ]
    assert data["omitted_by_parent"] == {"root": 2, "branch": 1, "focus": 1}
    assert {"source": "branch", "target": "focus", "kind": "lineage"} in data["edges"]
