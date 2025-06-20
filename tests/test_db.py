import os
import pytest
from cladecanvas.db import engine
from sqlalchemy import text

skip_on_ci = os.getenv("SKIP_API_TESTS") == "1"

@pytest.mark.skipif(skip_on_ci, reason="Skipping API tests on CI (no DB)")
def test_connection():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("Connection successful:", result.scalar() == 1)
    except Exception as e:
        print("Connection failed:", e)

if __name__ == "__main__":
    test_connection()