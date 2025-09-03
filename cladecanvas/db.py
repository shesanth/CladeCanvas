import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

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
