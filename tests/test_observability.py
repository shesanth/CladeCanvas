from fastapi import FastAPI
from fastapi.testclient import TestClient

from cladecanvas.observability import (
    REQUEST_ID_HEADER,
    RequestObservabilityMiddleware,
    metrics,
    record_cache_latency,
)


def test_request_middleware_sets_request_id_and_records_route_latency():
    metrics.reset()
    app = FastAPI()
    app.add_middleware(RequestObservabilityMiddleware)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/ping", headers={REQUEST_ID_HEADER: "test-request-id"})

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "test-request-id"

    snapshot = metrics.snapshot()
    assert snapshot["rollups"]["endpoint:GET /ping"]["count"] == 1
    assert snapshot["recent"][-1]["request_id"] == "test-request-id"


def test_cache_latency_primitive_records_hit_tag():
    metrics.reset()

    record_cache_latency("node", "get", 1.25, hit=True)

    snapshot = metrics.snapshot()
    assert snapshot["rollups"]["cache:node.get"]["count"] == 1
    assert snapshot["recent"][-1]["tags"] == {"hit": "true"}
