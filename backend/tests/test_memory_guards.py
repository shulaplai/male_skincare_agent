"""Guards for the memory rules that issue #19 found unguarded.

Mutation testing found these behaviours survived their own removal (the suite stayed
green): insight delete resurrecting a superseded predecessor, photo delete matching
`Photo.path` instead of `Photo.id`, the photo **file** disappearing from disk,
`get_skin_profile` including global-scope memory, `persist` honouring expiry,
`DECAY_DAYS == 30`, and `_COLUMN_MIGRATIONS` covering the model columns. Each test
below is written so it fails for the reason it names — the mutation angle is noted
where it is not obvious.

No real LLM is used: the graph is driven by the local `StubLLM` and the memory tool
takes a `DeterministicEmbedder`.
"""
import datetime
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import db as db_module
from app.agent import tools
from app.agent.graph import build_graph
from app.agent.schemas import Advice, SkinAnalysis
from app.config import settings
from app.db import Base, _COLUMN_MIGRATIONS, get_session
from app.main import app
from app.memory import DECAY_DAYS
from app.models import Conversation, Entry, Insight, Photo, Product, User, utcnow
from app.rag import DeterministicEmbedder

# Columns that were added to a table **after** it first shipped. Kept as an explicit
# mirror of `db._COLUMN_MIGRATIONS` so deleting a migration entry (the exact drift this
# guards) turns red instead of silently leaving old databases one column short.
EXPECTED_LATE_COLUMNS = {
    # persona（2026-10-21）＋ greet_enabled：全部係舊 DB 冇、要靠 migration 補嘅欄
    "users": {
        "photo_cloud_consent",
        "consent_at",
        "persona_gender",
        "persona_ethnicity",
        "persona_prompt",
        "greet_enabled",
    },
    "conversations": {"cloud_analysis"},
    "entries": {"attributes"},
    "insights": {"direction"},
    "timeline_events": {"source"},
    "chat_messages": {"provenance"},
}


@pytest.fixture
def api(tmp_path, monkeypatch):
    """TestClient on a throwaway DB + data dir (same shape as test_photo_orphans)."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine)

    def override():
        db = sf()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_session] = override
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    try:
        yield TestClient(app), sf, tmp_path
    finally:
        app.dependency_overrides.clear()


def seed_conversation(sf, body_part: str = "面部皮膚") -> str:
    s = sf()
    user = User(name="阿軒")
    s.add(user)
    s.flush()
    conv = Conversation(user_id=user.id, body_part=body_part, cloud_analysis=True)
    s.add(conv)
    s.commit()
    cid = conv.id
    s.close()
    return cid


def seed_entry(sf, cid: str, **kwargs) -> str:
    s = sf()
    entry = Entry(conversation_id=cid, date=kwargs.pop("date", datetime.date(2026, 1, 1)), **kwargs)
    s.add(entry)
    s.commit()
    eid = entry.id
    s.close()
    return eid


def memory_texts(sf, cid: str) -> list[str]:
    out = tools.run_tool(
        "get_skin_profile", {"conversation_id": cid}, sf(), DeterministicEmbedder()
    )
    return [row["text"] for row in out["result"]]


# ---------------------------------------------------------------------------
# a. Deleting an insight retires the predecessor instead of reviving it
# ---------------------------------------------------------------------------


def test_insight_delete_retires_the_predecessor(api):
    client, sf, _ = api
    cid = seed_conversation(sf)

    s = sf()
    successor = Insight(
        conversation_id=cid,
        kind="derived",
        tag="acne",
        direction="normal",
        text="暗瘡：正常",
        confidence=0.6,
        expires_at=datetime.datetime(2999, 1, 1),
    )
    s.add(successor)
    s.flush()
    predecessor = Insight(
        conversation_id=cid,
        kind="derived",
        tag="acne",
        direction="problem",
        text="暗瘡：中等",
        confidence=0.85,
        expires_at=datetime.datetime(2999, 1, 1),
        superseded_by=successor.id,
    )
    s.add(predecessor)
    s.commit()
    predecessor_id = predecessor.id
    successor_id = successor.id
    s.close()

    res = client.delete(f"/api/conversations/{cid}/insights/{successor_id}")
    assert res.status_code == 200, res.text

    s = sf()
    old = s.query(Insight).filter_by(id=predecessor_id).one()
    # No dangling pointer ...
    assert old.superseded_by is None
    # ... but the statement the deleted memory replaced must not become visible.
    assert old.expires_at is not None, "前任冇被即時到期，會喺讀取路徑復活"
    assert old.expires_at <= utcnow()
    s.close()

    summary = client.get(f"/api/conversations/{cid}/summary").json()
    assert [i["text"] for i in summary["insights"]] == []
    assert "暗瘡：中等" not in memory_texts(sf, cid)


# ---------------------------------------------------------------------------
# b. Expiry is honoured on both read paths
# ---------------------------------------------------------------------------


def test_expired_insight_hidden_from_summary_and_memory_tool(api):
    client, sf, _ = api
    cid = seed_conversation(sf)

    s = sf()
    s.add_all(
        [
            Insight(
                conversation_id=cid,
                kind="derived",
                tag="acne",
                direction="problem",
                text="暗瘡：中等（已過期）",
                confidence=0.85,
                expires_at=datetime.datetime(2020, 1, 1),
            ),
            Insight(
                conversation_id=cid,
                kind="derived",
                tag="oiliness",
                direction="normal",
                text="油光：正常",
                confidence=0.6,
                expires_at=datetime.datetime(2999, 1, 1),
            ),
        ]
    )
    s.commit()
    s.close()

    summary = client.get(f"/api/conversations/{cid}/summary").json()
    assert [i["text"] for i in summary["insights"]] == ["油光：正常"]
    assert "暗瘡：中等（已過期）" not in memory_texts(sf, cid)


def test_expired_global_insight_hidden_from_both_read_paths(api):
    """Global scope must not become a back door around the expiry filter."""
    client, sf, _ = api
    cid = seed_conversation(sf)

    s = sf()
    s.add(
        Insight(
            conversation_id=None,
            kind="fact",
            tag="user_fact",
            text="（已過期嘅 global 記憶）",
            expires_at=datetime.datetime(2020, 1, 1),
        )
    )
    s.commit()
    s.close()

    summary = client.get(f"/api/conversations/{cid}/summary").json()
    assert summary["insights"] == []
    assert "（已過期嘅 global 記憶）" not in memory_texts(sf, cid)


# ---------------------------------------------------------------------------
# c. Decay constant + persist honouring expiry
# ---------------------------------------------------------------------------


def test_decay_days_is_thirty():
    # The documented 30-day decay is the number users were told; drifting it
    # silently changes every memory's lifetime.
    assert DECAY_DAYS == 30


class StubLLM:
    """A minimal deterministic model: only what `graph` needs, never a network call."""

    def __init__(self, severity: int = 1):
        self.severity = severity

    def structured(self, system, user, schema):
        if schema is SkinAnalysis:
            return SkinAnalysis(
                observes_skin=True,
                summary="有觀察",
                attributes=[{"key": "acne", "severity": self.severity, "note": ""}],
            )
        return Advice(reply="建議如下。", items=["做好保濕"], disclaimer="已加免責", escalate=False)

    def structured_vision(self, system, user, schema, images):
        return self.structured(system, user, schema)


def test_persist_does_not_strengthen_an_expired_insight(api):
    """An expired row gets replaced, not refreshed — mutating the `is_expired` guard
    would bump its confidence and rewrite its text instead."""
    _client, sf, _ = api
    cid = seed_conversation(sf)
    expired_at = datetime.datetime(2020, 1, 1)

    s = sf()
    old = Insight(
        conversation_id=cid,
        kind="derived",
        tag="acne",
        direction="normal",
        text="暗瘡：舊讀數",
        confidence=0.85,
        expires_at=expired_at,
    )
    s.add(old)
    s.commit()
    old_id = old.id
    s.close()

    graph = build_graph(
        llm=StubLLM(severity=1), session_factory=sf, embedder=DeterministicEmbedder()
    )
    graph.invoke(
        {
            "conversation_id": cid,
            "user_text": "今日暗瘡好返啲",
            "photo_paths": [],
            "cloud_analysis": True,
            "trace": [],
        }
    )

    s = sf()
    rows = s.query(Insight).filter_by(conversation_id=cid, tag="acne").all()
    old = next(r for r in rows if r.id == old_id)
    assert old.text == "暗瘡：舊讀數", "過期 insight 被 strengthen（text 被更新）"
    assert old.confidence == 0.85, "過期 insight 被 strengthen（confidence 升咗）"
    assert old.expires_at == expired_at

    fresh = [r for r in rows if r.id != old_id]
    assert len(fresh) == 1, "過期之後應該另開一條新 insight，而唔係更新舊嗰條"
    assert fresh[0].expires_at > utcnow()
    s.close()


# ---------------------------------------------------------------------------
# d + g. Photo delete is keyed by path, and removes the file
# ---------------------------------------------------------------------------


def test_photo_delete_matches_path_not_photo_id(api):
    client, sf, _ = api
    cid = seed_conversation(sf)
    eid = seed_entry(sf, cid)
    path_id = "a" * 32  # what the route receives (derived from the path)
    row_id = "b" * 32  # deliberately different from the path's id

    s = sf()
    s.add(Photo(id=row_id, entry_id=eid, path=f"photos/{path_id}.jpg"))
    s.commit()
    s.close()

    res = client.delete(f"/api/entries/{eid}/photos/{path_id}")
    assert res.status_code == 200, res.text
    s = sf()
    assert s.query(Photo).filter_by(id=row_id).count() == 0, (
        "route 用 Photo.id 搵 row（而唔係 path），所以搵唔到 path 對應嗰行"
    )
    s.close()


def test_entry_photo_delete_removes_the_file_from_disk(api):
    client, sf, data_dir = api
    cid = seed_conversation(sf)
    eid = seed_entry(sf, cid)
    pid = "c" * 32

    # A realistic stored jpg; the route must unlink it, not only delete the row.
    (data_dir / "photos").mkdir(parents=True, exist_ok=True)
    buf = BytesIO()
    Image.new("RGB", (8, 8), (200, 150, 140)).save(buf, "JPEG")
    stored = data_dir / "photos" / f"{pid}.jpg"
    stored.write_bytes(buf.getvalue())
    s = sf()
    s.add(Photo(entry_id=eid, path=f"photos/{pid}.jpg"))
    s.commit()
    s.close()

    res = client.delete(f"/api/entries/{eid}/photos/{pid}")
    assert res.status_code == 200, res.text
    assert not stored.exists(), "刪咗 photo row 但檔案仍然喺 disk"


# ---------------------------------------------------------------------------
# e. Column migrations cover the model
# ---------------------------------------------------------------------------


def test_column_migrations_target_existing_model_columns():
    declared = {
        table: {name for name, _ddl in cols} for table, cols in _COLUMN_MIGRATIONS.items()
    }
    assert declared == EXPECTED_LATE_COLUMNS, (
        "db._COLUMN_MIGRATIONS 同已知嘅 late columns 唔一致（漏咗／多咗會令舊 DB 缺 column）"
    )
    for table, cols in _COLUMN_MIGRATIONS.items():
        model = Base.metadata.tables.get(table)
        assert model is not None, f"_COLUMN_MIGRATIONS 指向唔存在嘅 table {table}"
        for name, _ddl in cols:
            assert name in model.columns, f"{table}.{name} 喺 migration 但 model 冇"


def test_migrate_columns_repairs_a_table_missing_the_column(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    # Simulate an old database: every table exists with only its id column.
    with engine.begin() as conn:
        for table in _COLUMN_MIGRATIONS:
            conn.execute(text(f"CREATE TABLE {table} (id VARCHAR(32) PRIMARY KEY)"))

    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(settings, "database_url", "sqlite://")

    db_module._migrate_columns()

    have = {t: {c["name"] for c in inspect(engine).get_columns(t)} for t in _COLUMN_MIGRATIONS}
    for table, cols in _COLUMN_MIGRATIONS.items():
        for name, _ddl in cols:
            assert name in have[table], f"舊 table {table} 缺 {name}，migration 冇補返"


# ---------------------------------------------------------------------------
# f. Global memory reaches the coach; other conversations' memory does not
# ---------------------------------------------------------------------------


def test_skin_profile_includes_global_and_excludes_other_conversations(api):
    _client, sf, _ = api
    own = seed_conversation(sf, "面部皮膚")
    other = seed_conversation(sf, "背部皮膚")

    s = sf()
    s.add_all(
        [
            Insight(conversation_id=own, kind="derived", tag="acne", text="自己部位嘅記憶"),
            Insight(conversation_id=other, kind="derived", tag="acne", text="另一個部位嘅記憶"),
            Insight(conversation_id=None, kind="fact", tag="user_fact", text="全身都關事嘅記憶"),
        ]
    )
    s.commit()
    s.close()

    out = tools.run_tool(
        "get_skin_profile", {"conversation_id": own}, sf(), DeterministicEmbedder()
    )
    rows = {r["text"]: r for r in out["result"]}
    assert "自己部位嘅記憶" in rows
    assert "全身都關事嘅記憶" in rows
    assert rows["全身都關事嘅記憶"]["scope"] == "global"
    assert "另一個部位嘅記憶" not in rows, "coach 見到其他 conversation 嘅記憶"


# ---------------------------------------------------------------------------
# Product ids resolve to names in the entry payload (issue #19 face 3)
# ---------------------------------------------------------------------------


def test_summary_returns_product_names_beside_the_ids(api):
    client, sf, _ = api
    cid = seed_conversation(sf)

    s = sf()
    first = Product(conversation_id=cid, name="煙酰胺精華", category="精華")
    second = Product(conversation_id=cid, name="清爽防曬", category="防曬")
    s.add_all([first, second])
    s.commit()
    # Read ids while the session is live: Product rows expire on commit.
    second_id, first_id = second.id, first.id
    missing_id = "d" * 32
    # Entry.products keeps ids (self_report mutates by id); names are a display sibling.
    entry = Entry(
        conversation_id=cid,
        date=datetime.date(2026, 1, 2),
        attributes=[],
        products=[second_id, first_id, missing_id],
    )
    s.add(entry)
    s.commit()
    eid = entry.id
    s.close()

    body = client.get(f"/api/conversations/{cid}/summary").json()
    out = next(e for e in body["entries"] if e["id"] == eid)
    assert out["products"] == [second_id, first_id, missing_id]
    assert out["product_names"] == ["清爽防曬", "煙酰胺精華", missing_id], (
        "product_names 要跟 products 同序，缺產品 row 時 fallback 做 id"
    )
