import os

# Set a dummy POSTGRES_URL before any DB-dependent module is imported.
# This prevents db.py from raising RuntimeError at collection time.
# Tests marked @pytest.mark.api still need a real DB to actually run.
os.environ.setdefault("POSTGRES_URL", "postgresql://dummy:dummy@localhost:5432/dummy")
