import os
import sys

# Set a dummy POSTGRES_URL before any DB-dependent module is imported.
# This prevents db.py from raising RuntimeError at collection time.
# Tests marked @pytest.mark.api still need a real DB to actually run.
os.environ.setdefault("POSTGRES_URL", "postgresql://dummy:dummy@localhost:5432/dummy")

# Add project root to sys.path so `scripts/` is importable in tests.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
