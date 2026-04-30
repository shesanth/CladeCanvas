import os
import sys

# Set a dummy POSTGRES_URL before any DB-dependent module is imported unless
# the test run explicitly opts into the local read-only SQLite seed.
if os.environ.get("CLADECANVAS_DEV_SQLITE") != "1":
    os.environ.setdefault("POSTGRES_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

# Add project root to sys.path so `scripts/` is importable in tests.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
