"""Lightweight observability primitives for API and data access paths."""

from __future__ import annotations

import contextvars
import json
import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("cladecanvas.observability")

REQUEST_ID_HEADER = "X-Request-ID"
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


@dataclass(frozen=True)
class LatencySample:
    kind: str
    name: str
    latency_ms: float
    request_id: str | None
    tags: dict[str, str]


class LatencyMetrics:
    """In-memory latency rollup intended for local debugging and tests."""

    def __init__(self, max_samples: int = 500) -> None:
        self._samples: deque[LatencySample] = deque(maxlen=max_samples)
        self._counts: dict[str, int] = defaultdict(int)
        self._totals_ms: dict[str, float] = defaultdict(float)

    def record(
        self,
        kind: str,
        name: str,
        latency_ms: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        key = f"{kind}:{name}"
        self._counts[key] += 1
        self._totals_ms[key] += latency_ms
        self._samples.append(
            LatencySample(
                kind=kind,
                name=name,
                latency_ms=round(latency_ms, 3),
                request_id=get_request_id(),
                tags=tags or {},
            )
        )

    def snapshot(self) -> dict[str, Any]:
        rollups = {}
        for key, count in self._counts.items():
            total_ms = self._totals_ms[key]
            rollups[key] = {
                "count": count,
                "total_ms": round(total_ms, 3),
                "avg_ms": round(total_ms / count, 3) if count else 0,
            }
        return {
            "rollups": rollups,
            "recent": [asdict(sample) for sample in list(self._samples)[-25:]],
        }

    def reset(self) -> None:
        self._samples.clear()
        self._counts.clear()
        self._totals_ms.clear()


metrics = LatencyMetrics()


def configure_logging() -> None:
    root = logging.getLogger("cladecanvas")
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        root.addHandler(handler)
    root.setLevel(logging.INFO)


def get_request_id() -> str | None:
    return request_id_var.get()


def new_request_id() -> str:
    return uuid.uuid4().hex


def record_latency(
    kind: str,
    name: str,
    latency_ms: float,
    tags: dict[str, str] | None = None,
) -> None:
    metrics.record(kind, name, latency_ms, tags)


def record_cache_latency(
    cache_name: str,
    operation: str,
    latency_ms: float,
    hit: bool,
) -> None:
    record_latency(
        "cache",
        f"{cache_name}.{operation}",
        latency_ms,
        {"hit": str(hit).lower()},
    )


def log_event(event: str, **fields: Any) -> None:
    payload = {
        "event": event,
        "request_id": get_request_id(),
        **fields,
    }
    logger.info(json.dumps(payload, sort_keys=True, default=str))


class RequestObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or new_request_id()
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_code = 500
        response = None

        try:
            response = await call_next(request)
            status_code = response.status_code
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            route = request.scope.get("route")
            route_name = getattr(route, "path", request.url.path)
            record_latency(
                "endpoint",
                f"{request.method} {route_name}",
                elapsed_ms,
                {"status_code": str(status_code)},
            )
            log_event(
                "http_request",
                method=request.method,
                path=request.url.path,
                route=route_name,
                status_code=status_code,
                duration_ms=round(elapsed_ms, 3),
            )

            if response is not None:
                response.headers[REQUEST_ID_HEADER] = request_id
            request_id_var.reset(token)

        return response
