import os
import time
from collections import defaultdict, deque
from collections.abc import Callable
from threading import RLock
from typing import Any

from fastapi import HTTPException, Request, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


ANON_READ_RATE_LIMIT = int(os.environ.get("CLADECANVAS_ANON_READS_PER_MINUTE", "120"))
QUERY_TIMEOUT_MS = int(os.environ.get("CLADECANVAS_QUERY_TIMEOUT_MS", "3000"))
PUBLIC_CACHE_SECONDS = int(os.environ.get("CLADECANVAS_PUBLIC_CACHE_SECONDS", "60"))
STALE_REVALIDATE_SECONDS = int(os.environ.get("CLADECANVAS_STALE_REVALIDATE_SECONDS", "300"))
HOT_READ_CACHE_SECONDS = int(os.environ.get("CLADECANVAS_HOT_READ_CACHE_SECONDS", "30"))

MAX_BULK_NODE_IDS = int(os.environ.get("CLADECANVAS_MAX_BULK_NODE_IDS", "100"))
MAX_CHILDREN_LIMIT = int(os.environ.get("CLADECANVAS_MAX_CHILDREN_LIMIT", "200"))
MAX_SEARCH_LIMIT = int(os.environ.get("CLADECANVAS_MAX_SEARCH_LIMIT", "50"))
MAX_LINEAGE_DEPTH = int(os.environ.get("CLADECANVAS_MAX_LINEAGE_DEPTH", "128"))
MAX_SUBTREE_DEPTH = int(os.environ.get("CLADECANVAS_MAX_SUBTREE_DEPTH", "4"))
MAX_SUBTREE_NODES = int(os.environ.get("CLADECANVAS_MAX_SUBTREE_NODES", "500"))

_rate_windows: dict[str, deque[float]] = defaultdict(deque)
_rate_lock = RLock()


def rate_limit_anonymous_reads(request: Request) -> None:
    """Bound anonymous GET traffic per client without adding external services."""
    if request.method != "GET" or request.headers.get("authorization"):
        return

    client = request.client.host if request.client else "unknown"
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        client = forwarded_for.split(",", 1)[0].strip() or client

    now = time.monotonic()
    window_start = now - 60
    with _rate_lock:
        window = _rate_windows[client]
        while window and window[0] < window_start:
            window.popleft()
        if len(window) >= ANON_READ_RATE_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Anonymous read rate limit exceeded",
                headers={"Retry-After": "60"},
            )
        window.append(now)


class TTLCache:
    def __init__(self, ttl_seconds: int = HOT_READ_CACHE_SECONDS, max_entries: int = 512) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._entries: dict[tuple[Any, ...], tuple[float, Any]] = {}
        self._lock = RLock()

    def get_or_set(self, key: tuple[Any, ...], loader: Callable[[], Any]) -> Any:
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry and entry[0] > now:
                return entry[1]

        value = loader()
        with self._lock:
            if len(self._entries) >= self.max_entries:
                self._prune(now)
            self._entries[key] = (now + self.ttl_seconds, value)
        return value

    def _prune(self, now: float) -> None:
        expired = [key for key, (expires_at, _) in self._entries.items() if expires_at <= now]
        for key in expired:
            self._entries.pop(key, None)
        while len(self._entries) >= self.max_entries:
            self._entries.pop(next(iter(self._entries)))


hot_read_cache = TTLCache()


def set_public_cache_headers(response: Response, max_age: int = PUBLIC_CACHE_SECONDS) -> None:
    response.headers["Cache-Control"] = (
        f"public, max-age={max_age}, stale-while-revalidate={STALE_REVALIDATE_SECONDS}"
    )
    response.headers["Vary"] = "Accept-Encoding"


def apply_statement_timeout(db: Session) -> None:
    """Apply a per-transaction Postgres timeout when the backend supports it."""
    try:
        db.execute(text("SET LOCAL statement_timeout = :timeout_ms"), {"timeout_ms": QUERY_TIMEOUT_MS})
    except SQLAlchemyError:
        db.rollback()

