import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from cladecanvas.observability import record_latency

# Load from .env file if present
load_dotenv()

"""Database connection setup for CladeCanvas."""

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DEV_SQLITE_PATH = PROJECT_ROOT / "data" / "dev_seed.sqlite"


@dataclass(frozen=True)
class DatabaseProfile:
    name: str
    url: str
    read_only: bool
    writes_allowed: bool


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _sqlite_readonly_url(path: Path) -> str:
    sqlite_path = path.resolve().as_posix()
    return f"sqlite:///file:{sqlite_path}?mode=ro&uri=true"


def resolve_database_profile() -> DatabaseProfile:
    """Resolve database mode from environment."""
    explicit_profile = os.environ.get("CLADECANVAS_DB_PROFILE", "").strip().lower()
    dev_sqlite = explicit_profile == "dev-sqlite" or _truthy(os.environ.get("CLADECANVAS_DEV_SQLITE"))

    if dev_sqlite:
        sqlite_path = Path(os.environ.get("CLADECANVAS_SQLITE_PATH", DEFAULT_DEV_SQLITE_PATH))
        if not sqlite_path.exists():
            raise RuntimeError(
                "CLADECANVAS_DEV_SQLITE=1 requested, but the SQLite seed DB was not found at "
                f"{sqlite_path}. Expected data/dev_seed.sqlite or set CLADECANVAS_SQLITE_PATH."
            )
        return DatabaseProfile(
            name="dev-sqlite",
            url=_sqlite_readonly_url(sqlite_path),
            read_only=True,
            writes_allowed=False,
        )

    db_url = os.environ.get("POSTGRES_URL", "").strip()
    if not db_url:
        raise RuntimeError(
            "POSTGRES_URL environment variable not set. For local read-only API work, "
            "set CLADECANVAS_DEV_SQLITE=1 to use data/dev_seed.sqlite."
        )

    profile_name = explicit_profile or os.environ.get("CLADECANVAS_ENV", "dev-postgres").strip().lower()
    if profile_name not in {"prod", "dev-postgres"}:
        raise RuntimeError(
            f"Unsupported CLADECANVAS_DB_PROFILE={profile_name!r}. "
            "Use prod, dev-postgres, or dev-sqlite."
        )
    return DatabaseProfile(name=profile_name, url=db_url, read_only=False, writes_allowed=True)


profile = resolve_database_profile()
connect_args = {"check_same_thread": False} if profile.name == "dev-sqlite" else {}

# SQLAlchemy engine and session factory
engine = create_engine(profile.url, echo=False, connect_args=connect_args)
Session = sessionmaker(bind=engine)

logger.warning(
    "CladeCanvas database mode: %s%s",
    profile.name,
    " (read-only API seed; enrichment/write paths disabled)" if profile.read_only else "",
)


def assert_writes_allowed(operation: str = "write operation") -> None:
    if not profile.writes_allowed:
        raise RuntimeError(
            f"{operation} is disabled in {profile.name} mode. "
            "Unset CLADECANVAS_DEV_SQLITE and configure POSTGRES_URL for enrichment or data writes."
        )


@event.listens_for(engine, "before_cursor_execute")
def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._cladecanvas_query_started = time.perf_counter()


@event.listens_for(engine, "after_cursor_execute")
def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    started = getattr(context, "_cladecanvas_query_started", None)
    if started is None:
        return
    elapsed_ms = (time.perf_counter() - started) * 1000
    operation = statement.lstrip().split(maxsplit=1)[0].lower() if statement else "unknown"
    record_latency("db", operation, elapsed_ms, {"executemany": str(executemany).lower()})
