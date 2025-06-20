import pytest
from sqlalchemy import text

@pytest.mark.api
def test_connection():
    from cladecanvas.db import engine
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("Connection successful:", result.scalar() == 1)
    except Exception as e:
        print("Connection failed:", e)

if __name__ == "__main__":
    test_connection()
