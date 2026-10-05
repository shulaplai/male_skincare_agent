"""An old database must be repaired in place, or global writes die silently (#16).

`init_db()` has rebuilt stale `NOT NULL` columns since commit `3b008b1` (2026-10-01),
but nothing exercised it: the only evidence was one manual check on a copy of the live
DB (`docs/open-findings.md`), which is why the docs claimed it "✅ offline / 🟡 never
verified". These tests are that missing evidence.

Why it matters: commit `7d0ce75` made `Insight.conversation_id` and
`TimelineEvent.conversation_id` nullable so global-scope rows could exist (Q31:
body-spanning diet/sleep events, global facts, global preferences). A database created
before it kept `NOT NULL`, and every global write then failed with
`IntegrityError: NOT NULL constraint failed` — the diet timeline, global facts and
global preferences were silently dead. Every *read* still returned 200, and "no rows
yet" looks exactly like "writes are being rejected", so nothing surfaced in the UI.
If the rebuild ever stops working, that failure comes back on every pre-2026-10-01 DB
with no signal again.

The legacy DDL below is copied **verbatim** from `sqlite_master` of
`data/skincoach.db.bak` (2026-09-30), so the fixture is the shape production actually
shipped — not one invented to make the rebuild look good.
"""
import datetime
import sqlite3

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app import db
from app.config import settings
from app.db import get_session
from app.main import app
from app.models import Conversation, User

LEGACY_TIMELINE_EVENTS = """CREATE TABLE timeline_events (
	id VARCHAR(32) NOT NULL,
	conversation_id VARCHAR(32) NOT NULL,
	date DATE NOT NULL,
	text TEXT NOT NULL,
	created_at DATETIME NOT NULL,
	source VARCHAR(20) NOT NULL DEFAULT 'user',
	PRIMARY KEY (id),
	FOREIGN KEY(conversation_id) REFERENCES conversations (id)
)"""

# The same table as it looked *before* `_COLUMN_MIGRATIONS` added `source`.
LEGACY_TIMELINE_EVENTS_BEFORE_SOURCE = LEGACY_TIMELINE_EVENTS.replace(
    "\tsource VARCHAR(20) NOT NULL DEFAULT 'user',\n", ""
)

LEGACY_INSIGHTS = """CREATE TABLE insights (
	id VARCHAR(32) NOT NULL,
	conversation_id VARCHAR(32) NOT NULL,
	kind VARCHAR(20) NOT NULL,
	tag VARCHAR(120) NOT NULL,
	text TEXT NOT NULL,
	confidence FLOAT,
	expires_at DATETIME,
	superseded_by VARCHAR(32),
	version INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	direction VARCHAR(20) NOT NULL DEFAULT '',
	PRIMARY KEY (id),
	FOREIGN KEY(conversation_id) REFERENCES conversations (id),
	FOREIGN KEY(superseded_by) REFERENCES insights (id)
)"""

LEGACY_INDEXES = (
    "CREATE INDEX ix_timeline_events_conversation_id ON timeline_events (conversation_id)",
    "CREATE INDEX ix_insights_conversation_id ON insights (conversation_id)",
)

# (id, conversation_id, date, text)
LEGACY_EVENTS = (
    ("1" * 32, "f" * 32, datetime.date(2026, 9, 29), "打邊爐"),
    ("2" * 32, "f" * 32, datetime.date(2026, 9, 30), "通頂兩點先瞓"),
)

# (id, conversation_id, kind, tag, text, confidence, version, direction)
LEGACY_INSIGHT_ROWS = (
    ("a" * 32, "f" * 32, "fact", "skin_type", "混合偏油", None, 1, ""),
    ("b" * 32, "f" * 32, "derived", "acne", "下巴有兩粒", 0.6, 1, "problem"),
)


def build_legacy_db(path, timeline_events_ddl: str = LEGACY_TIMELINE_EVENTS) -> None:
    """Write a database in the pre-`3b008b1` shape, with rows in both tables."""
    has_source = "source" in timeline_events_ddl
    con = sqlite3.connect(path)
    try:
        con.execute(timeline_events_ddl)
        con.execute(LEGACY_INSIGHTS)
        for ddl in LEGACY_INDEXES:
            con.execute(ddl)
        cols = "id, conversation_id, date, text, created_at" + (", source" if has_source else "")
        extra = ",'user'" if has_source else ""
        events = [(eid, cid, d.isoformat(), txt) for eid, cid, d, txt in LEGACY_EVENTS]
        con.executemany(
            f"INSERT INTO timeline_events ({cols}) VALUES (?,?,?,?,'2026-09-30 12:00:00'{extra})",
            events,
        )
        con.executemany(
            "INSERT INTO insights (id, conversation_id, kind, tag, text, confidence, version,"
            " direction, created_at) VALUES (?,?,?,?,?,?,?,?, '2026-09-30 12:00:00')",
            LEGACY_INSIGHT_ROWS,
        )
        con.commit()
    finally:
        con.close()


@pytest.fixture
def legacy(tmp_path, monkeypatch):
    """A throwaway DB in the legacy shape, wired into `app.db` as the live engine.

    `app.db.engine` is a module global, so patching the attribute is what redirects
    every migration helper — and the app's own startup `init_db()` — to the fixture.
    """
    path = tmp_path / "legacy.db"
    build_legacy_db(path)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    sf = sessionmaker(bind=engine)
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{path}")
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(db, "engine", engine)

    def override():
        session = sf()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override
    try:
        yield engine, sf
    finally:
        app.dependency_overrides.clear()


def rows(engine, sql: str) -> list:
    with engine.connect() as conn:
        return [tuple(r) for r in conn.execute(text(sql)).all()]


def test_init_db_relaxes_not_null_and_keeps_every_row(legacy):
    engine, _ = legacy

    db.init_db()

    for table in ("timeline_events", "insights"):
        columns = {c["name"]: c for c in inspect(engine).get_columns(table)}
        assert columns["conversation_id"]["nullable"] is True, (
            f"{table}.conversation_id is still NOT NULL — global writes will fail with "
            "IntegrityError again"
        )

    # The rows must survive the create → copy → drop → rename dance, values intact.
    assert rows(engine, "SELECT id, text, source FROM timeline_events ORDER BY id") == [
        ("1" * 32, "打邊爐", "user"),
        ("2" * 32, "通頂兩點先瞓", "user"),
    ]
    assert rows(
        engine, "SELECT id, kind, confidence, direction FROM insights ORDER BY id"
    ) == [
        ("a" * 32, "fact", None, ""),
        ("b" * 32, "derived", 0.6, "problem"),
    ]

    # Dropping the old table took its indexes with it, so they have to be recreated.
    assert {i["name"] for i in inspect(engine).get_indexes("timeline_events")} == {
        "ix_timeline_events_conversation_id"
    }
    assert {i["name"] for i in inspect(engine).get_indexes("insights")} == {
        "ix_insights_conversation_id"
    }


def test_a_second_startup_is_a_no_op(legacy):
    """Every start runs this path — it must not rebuild or lose rows when nothing is stale."""
    engine, _ = legacy

    db.init_db()
    before = rows(engine, "SELECT id, text FROM timeline_events ORDER BY id")

    assert db._rebuild_stale_nullables() == []
    db.init_db()

    assert rows(engine, "SELECT id, text FROM timeline_events ORDER BY id") == before
    assert rows(engine, "SELECT COUNT(*) FROM insights") == [(2,)]


def test_the_app_startup_repairs_the_db_and_a_global_fact_is_accepted(legacy):
    """The production path end to end: lifespan → init_db → `POST …/facts {global_scope}`.

    This is the request that used to answer 500 `NOT NULL constraint failed`.
    """
    engine, _ = legacy

    with TestClient(app) as client:
        res = client.post(
            f"/api/conversations/{'f' * 32}/facts",
            json={"text": "最近轉咗用溫和潔面", "tag": "routine", "global_scope": True},
        )
        assert res.status_code == 200, res.text
        assert res.json()["scope"] == "global"

    assert rows(engine, "SELECT COUNT(*) FROM insights WHERE conversation_id IS NULL") == [(1,)]
    assert rows(
        engine, "SELECT text, tag FROM insights WHERE conversation_id IS NULL"
    ) == [("最近轉咗用溫和潔面", "routine")]


def test_the_app_startup_repairs_the_db_and_a_global_diet_event_is_accepted(legacy):
    """Diet events are the other global write: `TimelineEvent(conversation_id=None)`."""
    engine, sf = legacy

    with TestClient(app) as client:
        session = sf()
        user = User(name="阿軒")
        session.add(user)
        session.flush()
        conv = Conversation(user_id=user.id, body_part="面部皮膚", cloud_analysis=True)
        session.add(conv)
        session.commit()
        cid = conv.id
        session.close()

        res = client.post(
            f"/api/conversations/{cid}/events",
            json={"events": [{"type": "diet", "text": "打邊爐辣底"}]},
        )
        assert res.status_code == 200, res.text
        assert res.json()["written"] == 1

    assert rows(
        engine,
        "SELECT text, source FROM timeline_events WHERE conversation_id IS NULL",
    ) == [("打邊爐辣底", "user")]


def test_an_older_table_missing_a_model_column_still_rebuilds(tmp_path, monkeypatch):
    """`_migrate_columns` must run *before* the rebuild, so an old table's new column is copied.

    `source` was added by `_COLUMN_MIGRATIONS` after these tables first shipped, so a
    real legacy DB can be missing it; the rebuild then copies the intersection of both
    column sets, and the ADD COLUMN default must land in the copied rows.
    """
    path = tmp_path / "older.db"
    build_legacy_db(path, LEGACY_TIMELINE_EVENTS_BEFORE_SOURCE)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{path}")
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(db, "engine", engine)

    db.init_db()

    assert "source" in {c["name"] for c in inspect(engine).get_columns("timeline_events")}
    assert {c["name"]: c for c in inspect(engine).get_columns("timeline_events")}[
        "conversation_id"
    ]["nullable"] is True
    assert rows(engine, "SELECT id, text, source FROM timeline_events ORDER BY id") == [
        ("1" * 32, "打邊爐", "user"),
        ("2" * 32, "通頂兩點先瞓", "user"),
    ]
