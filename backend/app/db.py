"""Database engine, session factory and schema bootstrap.

Local-first: a single SQLite file under `data/`. The storage layer is isolated
here so it can be swapped for Postgres + pgvector without touching the rest of
the app (the interview answer, not just a comment).
"""
import logging
import os

from sqlalchemy import MetaData, Table, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.schema import CreateIndex, CreateTable

from .config import settings

logger = logging.getLogger(__name__)


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


# Column *shape* changes that `ALTER TABLE` cannot express on SQLite. Dropping
# NOT NULL needs the full rebuild dance (create → copy → drop → rename), so these
# are declared separately from the ADD COLUMN list above.
#
# Why this exists: commit 7d0ce75 made `conversation_id` nullable on `insights`
# and `timeline_events` so global-scope rows could exist (Q31: body-spanning diet
# and sleep events, global facts, global preferences). Databases created before it
# kept `NOT NULL` and nothing could migrate that, so every global write failed with
# `IntegrityError: NOT NULL constraint failed` — silently disabling the diet
# timeline, global facts and global preferences, while every read path still
# returned 200 (the empty state simply looked like "no data yet"). `init_db()`
# now repairs those tables in place, preserving rows.
_NULLABLE_REBUILDS: dict[str, list[str]] = {
    "insights": ["conversation_id"],
    "timeline_events": ["conversation_id"],
}


def _rebuild_table(table: Table, shared: list[str]) -> None:
    """Rebuild one table so the model's column definitions win, then restore indexes."""
    tmp_name = f"{table.name}__rebuild"
    tmp = table.to_metadata(MetaData(), name=tmp_name)
    columns = ", ".join(shared)
    # Copy into the *live* metadata (not a fresh one) so the copies' foreign keys
    # can still resolve their target tables; `MetaData.remove` undoes the copy in
    # finally so `create_all` never sees the temporary name.
    tmp = table.to_metadata(Base.metadata, name=tmp_name)
    try:
        with engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {tmp_name}"))
            conn.execute(text(str(CreateTable(tmp).compile(dialect=engine.dialect))))
            conn.execute(
                text(f"INSERT INTO {tmp_name} ({columns}) SELECT {columns} FROM {table.name}")
            )
            conn.execute(text(f"DROP TABLE {table.name}"))
            conn.execute(text(f"ALTER TABLE {tmp_name} RENAME TO {table.name}"))
            # Dropping the old table took its indexes with it.
            for index in table.indexes:
                conn.execute(text(str(CreateIndex(index).compile(dialect=engine.dialect))))
    finally:
        Base.metadata.remove(tmp)


def _rebuild_stale_nullables() -> list[str]:
    """Rebuild tables where the DB still enforces NOT NULL but the model allows NULL."""
    if not settings.database_url.startswith("sqlite"):
        return []
    inspector = inspect(engine)
    existing = {
        t: {c["name"]: c for c in inspector.get_columns(t)} for t in inspector.get_table_names()
    }
    rebuilt: list[str] = []
    for table_name, watched in _NULLABLE_REBUILDS.items():
        if table_name not in existing:
            continue
        table = Base.metadata.tables.get(table_name)
        if table is None:
            continue
        # Only relax columns the model actually declares nullable — a model that
        # still wants NOT NULL keeps it.
        stale = [
            name
            for name in watched
            if name in existing[table_name]
            and not existing[table_name][name].get("nullable", True)
            and table.columns[name].nullable
        ]
        if not stale:
            continue
        # Copy only columns both sides know about, so an older table missing a
        # model column cannot break the INSERT.
        shared = [c.name for c in table.columns if c.name in existing[table_name]]
        _rebuild_table(table, shared)
        rebuilt.append(f"{table_name}({', '.join(stale)})")
    if rebuilt:
        logger.warning(
            "init_db: rebuilt tables to relax NOT NULL — global-scope writes were failing: %s",
            ", ".join(rebuilt),
        )
    return rebuilt


def init_db() -> None:
    # Ensure the data dir (SQLite + photos) exists before the engine touches it.
    os.makedirs(settings.data_dir, exist_ok=True)
    from . import models  # noqa: F401  (register all models on Base.metadata)

    Base.metadata.create_all(bind=engine)
    _migrate_columns()
    _rebuild_stale_nullables()


def get_session():
    """FastAPI dependency yielding a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
