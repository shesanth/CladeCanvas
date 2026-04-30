from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from cladecanvas.api import hardening
from cladecanvas.api.main import app
from cladecanvas.api.routes.tree import get_db as get_tree_db
from cladecanvas.schema import metadata_table, nodes
from scripts.verify_db_indexes import REQUIRED_INDEXES


def test_read_path_indexes_are_declared_in_schema():
    node_indexes = {index.name for index in nodes.indexes}
    metadata_indexes = {index.name for index in metadata_table.indexes}

    assert REQUIRED_INDEXES["nodes"] <= node_indexes
    assert REQUIRED_INDEXES["metadata"] <= metadata_indexes


def test_anonymous_read_rate_limit_blocks_after_window(monkeypatch):
    monkeypatch.setattr(hardening, "ANON_READ_RATE_LIMIT", 2)
    hardening._rate_windows.clear()
    request = SimpleNamespace(
        method="GET",
        headers={},
        client=SimpleNamespace(host="203.0.113.7"),
    )

    hardening.rate_limit_anonymous_reads(request)
    hardening.rate_limit_anonymous_reads(request)

    with pytest.raises(HTTPException) as excinfo:
        hardening.rate_limit_anonymous_reads(request)
    assert excinfo.value.status_code == 429


def test_authorized_reads_skip_anonymous_rate_limit(monkeypatch):
    monkeypatch.setattr(hardening, "ANON_READ_RATE_LIMIT", 0)
    hardening._rate_windows.clear()
    request = SimpleNamespace(
        method="GET",
        headers={"authorization": "Bearer test"},
        client=SimpleNamespace(host="203.0.113.8"),
    )

    hardening.rate_limit_anonymous_reads(request)


def test_ttl_cache_reuses_hot_read_until_expiry():
    cache = hardening.TTLCache(ttl_seconds=60, max_entries=4)
    calls = 0

    def load_value():
        nonlocal calls
        calls += 1
        return {"value": calls}

    assert cache.get_or_set(("key",), load_value) == {"value": 1}
    assert cache.get_or_set(("key",), load_value) == {"value": 1}
    assert calls == 1


def test_children_endpoint_exposes_pagination_headers():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    nodes.create(engine)
    SessionLocal = sessionmaker(bind=engine)

    with engine.begin() as conn:
        conn.execute(
            insert(nodes),
            [
                {"node_id": "parent", "name": "Parent", "parent_node_id": None},
                {"node_id": "child-1", "name": "Child 1", "parent_node_id": "parent"},
                {"node_id": "child-2", "name": "Child 2", "parent_node_id": "parent"},
                {"node_id": "child-3", "name": "Child 3", "parent_node_id": "parent"},
            ],
        )

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    hardening.hot_read_cache._entries.clear()
    hardening._rate_windows.clear()
    app.dependency_overrides[get_tree_db] = override_get_db
    try:
        client = TestClient(app)
        response = client.get("/tree/children/parent?limit=2&offset=0")
    finally:
        app.dependency_overrides.clear()
        hardening.hot_read_cache._entries.clear()

    assert response.status_code == 200
    assert [child["node_id"] for child in response.json()] == ["child-1", "child-2"]
    assert response.headers["X-Total-Count"] == "3"
    assert response.headers["X-Limit"] == "2"
    assert response.headers["X-Offset"] == "0"
    assert response.headers["X-Has-More"] == "true"


def test_children_endpoint_marks_last_page_not_truncated():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    nodes.create(engine)
    SessionLocal = sessionmaker(bind=engine)

    with engine.begin() as conn:
        conn.execute(
            insert(nodes),
            [
                {"node_id": "parent", "name": "Parent", "parent_node_id": None},
                {"node_id": "child-1", "name": "Child 1", "parent_node_id": "parent"},
                {"node_id": "child-2", "name": "Child 2", "parent_node_id": "parent"},
            ],
        )

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    hardening.hot_read_cache._entries.clear()
    hardening._rate_windows.clear()
    app.dependency_overrides[get_tree_db] = override_get_db
    try:
        client = TestClient(app)
        response = client.get("/tree/children/parent?limit=2&offset=1")
    finally:
        app.dependency_overrides.clear()
        hardening.hot_read_cache._entries.clear()

    assert response.status_code == 200
    assert [child["node_id"] for child in response.json()] == ["child-2"]
    assert response.headers["X-Total-Count"] == "2"
    assert response.headers["X-Limit"] == "2"
    assert response.headers["X-Offset"] == "1"
    assert response.headers["X-Has-More"] == "false"
