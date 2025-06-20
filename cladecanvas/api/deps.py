from cladecanvas.db import Session as SessionLocal

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
