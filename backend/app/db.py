"""Database engine, session factory and schema bootstrap.

Local-first: a single SQLite file under `data/`. The storage layer is isolated
here so it can be swapped for Postgres + pgvector without touching the rest of
the app (the interview answer, not just a comment).
"""
import datetime
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
    "users": [
        ("photo_cloud_consent", "BOOLEAN NOT NULL DEFAULT 0"),
        ("consent_at", "DATETIME"),
    ],
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
    _normalise_cloud_only_policy()
    _normalise_consent_policy()


def _normalise_cloud_only_policy() -> None:
    """Cloud-only decision (2026-10-01): the per-conversation mode flag is gone.

    The app can no longer be in "local" mode, so a row that still says
    `cloud_analysis = 0` would be describing a state the product no longer has.
    Normalise it once at startup instead of leaving a lie in the DB (this touches
    one policy flag only — never user content). The actual consent gate is
    `User.photo_cloud_consent`, which this deliberately does **not** set: consent
    must come from the user, not from a migration.
    """
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.begin() as conn:
        conn.execute(text("UPDATE conversations SET cloud_analysis = 1 WHERE cloud_analysis = 0"))


def _normalise_consent_policy() -> None:
    """Self-host consent default (2026-10-01): consent counts as given.

    A database created before the switch has `photo_cloud_consent = 0`, which would
    keep the consent screen (and the server-side gate) blocking the only user of
    this deployment. When the policy does not require an explicit tick, backfill it
    once — with the timestamp, so the row still records *when* consent started.
    Skipped entirely when `SKINCOACH_REQUIRE_PHOTO_CONSENT=true`.
    """
    if not settings.database_url.startswith("sqlite") or settings.require_photo_consent:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                # 只補「從來冇同意過」嘅 row（`consent_at IS NULL`）：自願撤回嘅
                # row 會 retain `consent_at`，唔可以幫佢哋自動開返。
                "UPDATE users SET photo_cloud_consent = 1, consent_at = :now "
                "WHERE photo_cloud_consent = 0 AND consent_at IS NULL"
            ),
            {"now": datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)},
        )


def get_session():
    """FastAPI dependency yielding a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
