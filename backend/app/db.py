"""Database engine, session factory and schema bootstrap.

Local-first: a single SQLite file under `data/`. The storage layer is isolated
here so it can be swapped for Postgres + pgvector without touching the rest of
the app (the interview answer, not just a comment).
"""
import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# New columns added after a table was first created. `create_all` never alters
# existing tables, so we ALTER TABLE here — this preserves the local corpus DB.
_COLUMN_MIGRATIONS: dict[str, list[tuple[str, str]]] = {
    "conversations": [
        ("cloud_analysis", "BOOLEAN NOT NULL DEFAULT 0"),
    ],
    "entries": [
        ("attributes", "JSON"),
    ],
    "insights": [
        ("direction", "VARCHAR(20) NOT NULL DEFAULT ''"),
    ],
    "timeline_events": [
        ("source", "VARCHAR(20) NOT NULL DEFAULT 'user'"),
    ],
}


def _migrate_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    existing = {t: {c["name"] for c in inspector.get_columns(t)} for t in inspector.get_table_names()}
    with engine.begin() as conn:
        for table, cols in _COLUMN_MIGRATIONS.items():
            if table not in existing:
                continue
            have = existing[table]
            for name, ddl in cols:
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def init_db() -> None:
    # Ensure the data dir (SQLite + photos) exists before the engine touches it.
    os.makedirs(settings.data_dir, exist_ok=True)
    from . import models  # noqa: F401  (register all models on Base.metadata)

    Base.metadata.create_all(bind=engine)
    _migrate_columns()


def get_session():
    """FastAPI dependency yielding a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
