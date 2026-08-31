"""Database engine, session factory and schema bootstrap.

Local-first: a single SQLite file under `data/`. The storage layer is isolated
here so it can be swapped for Postgres + pgvector without touching the rest of
the app (the interview answer, not just a comment).
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    # Ensure the data dir (SQLite + photos) exists before the engine touches it.
    os.makedirs(settings.data_dir, exist_ok=True)
    from . import models  # noqa: F401  (register all models on Base.metadata)

    Base.metadata.create_all(bind=engine)


def get_session():
    """FastAPI dependency yielding a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
