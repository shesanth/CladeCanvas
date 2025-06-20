import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load from .env file if present
load_dotenv()

DEFAULT_DB_URL = ""

# Use env var or fallback
DB_URL = os.environ.get("POSTGRES_URL", DEFAULT_DB_URL)

# SQLAlchemy engine and session factory
engine = create_engine(DB_URL, echo=False)
Session = sessionmaker(bind=engine)