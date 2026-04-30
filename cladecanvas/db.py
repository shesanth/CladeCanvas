import os
import time
from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from cladecanvas.observability import record_latency

# Load from .env file if present
load_dotenv()

"""Database connection setup for CladeCanvas."""

# Default to no URL so we can detect a misconfiguration.
DEFAULT_DB_URL = ""

# Use environment variable if provided
DB_URL = os.environ.get("POSTGRES_URL", DEFAULT_DB_URL)

if not DB_URL:
    raise RuntimeError(
        "POSTGRES_URL environment variable not set. "
        "Please provide a valid SQLAlchemy database URL."
    )

# SQLAlchemy engine and session factory
engine = create_engine(DB_URL, echo=False)
Session = sessionmaker(bind=engine)


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
