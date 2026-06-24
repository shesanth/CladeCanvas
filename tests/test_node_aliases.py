from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _client_with_alias_db():
    from cladecanvas.api.deps import get_db
    from cladecanvas.api.main import app
    from cladecanvas.schema import metadata, metadata_table, node_aliases, nodes

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with engine.begin() as conn:
        conn.execute(insert(nodes), [
            {"node_id": "root", "name": "Root", "parent_node_id": None, "child_count": 2, "has_metadata": 0, "num_tips": 100},
            {"node_id": "canonical", "name": "A + B", "parent_node_id": "root", "child_count": 1, "has_metadata": 1, "num_tips": 50, "display_name": "AliasName"},
            {"node_id": "alias", "ott_id": 1, "name": "AliasName", "parent_node_id": "root", "child_count": 1, "has_metadata": 1, "num_tips": None},
            {"node_id": "alias-child", "ott_id": 2, "name": "Alias Child", "parent_node_id": "alias", "child_count": 0, "has_metadata": 0, "num_tips": 1},
            {"node_id": "canonical-child", "ott_id": 3, "name": "Canonical Child", "parent_node_id": "canonical", "child_count": 0, "has_metadata": 0, "num_tips": 1},
        ])
        conn.execute(insert(node_aliases), [{
            "alias_node_id": "alias",
            "canonical_node_id": "canonical",
            "reason": "test",
            "confidence": 1.0,
        }])
        conn.execute(insert(metadata_table), [
            {
                "node_id": "canonical",
                "ott_id": None,
                "common_name": "AliasName",
                "description": "canonical clade metadata",
                "full_description": "The canonical clade contains the alias child.",
                "image_url": None,
                "wiki_page_url": None,
                "enriched_score": 1.0,
            },
            {
                "node_id": "alias",
                "ott_id": 1,
                "common_name": "AliasName",
                "description": "alias metadata",
                "full_description": None,
                "image_url": None,
                "wiki_page_url": None,
                "enriched_score": 1.0,
            },
        ])

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return app, TestClient(app)


def test_node_alias_resolves_struct_and_metadata():
    app, client = _client_with_alias_db()
    try:
        node_response = client.get("/node/alias")
        metadata_response = client.get("/node/metadata/alias")
    finally:
        app.dependency_overrides.clear()

    assert node_response.status_code == 200
    assert node_response.json()["node_id"] == "canonical"
    assert metadata_response.status_code == 200
    assert metadata_response.json()["node_id"] == "canonical"
    assert metadata_response.json()["description"] == "canonical clade metadata"


def test_children_and_lineage_treat_alias_parent_as_canonical():
    app, client = _client_with_alias_db()
    try:
        children_response = client.get("/tree/children/canonical?limit=10")
        lineage_response = client.get("/tree/lineage/alias-child")
    finally:
        app.dependency_overrides.clear()

    assert children_response.status_code == 200
    child_ids = [node["node_id"] for node in children_response.json()]
    assert "alias" not in child_ids
    assert child_ids == ["alias-child", "canonical-child"]

    assert lineage_response.status_code == 200
    lineage_ids = [node["node_id"] for node in lineage_response.json()["lineage"]]
    assert lineage_ids == ["root", "canonical", "alias-child"]


def test_search_dedupes_alias_to_canonical():
    app, client = _client_with_alias_db()
    try:
        response = client.get("/search?q=AliasName&limit=10")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    ids = [row["node_id"] for row in response.json()]
    assert ids == ["canonical"]

def test_context_graph_excludes_alias_equivalents_from_siblings():
    app, client = _client_with_alias_db()
    try:
        response = client.get("/tree/context/alias-child?sibling_limit=10&child_limit=10")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    lineage_ids = [node["node_id"] for node in data["lineage"]]
    sibling_ids = [node["node_id"] for node in data["nodes"] if node["kind"] == "sibling"]

    assert lineage_ids == ["root", "canonical", "alias-child"]
    assert "alias" not in sibling_ids
    assert "canonical" not in sibling_ids
