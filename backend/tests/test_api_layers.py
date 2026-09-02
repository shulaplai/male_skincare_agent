"""API-level tests for Layer 2/3 routes: global-scope summary, correlations,
delete/edit memory-correction endpoints (Q30/Q31/Q52)."""
import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_session
from app.main import app
from app.models import Conversation, Entry, Insight, Photo, Product, TimelineEvent, User

D = datetime.date


def make_env():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # one shared in-memory DB across every session
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

    session = sf()
    u = User(name="阿軒")
    session.add(u)
    session.flush()
    c1 = Conversation(user_id=u.id, body_part="面部皮膚", cloud_analysis=True)
    c2 = Conversation(user_id=u.id, body_part="頭皮", cloud_analysis=True)
    session.add_all([c1, c2])
    session.commit()
    cid1, cid2 = c1.id, c2.id

    # Entries for conversation 1 across a few days.
    session.add_all(
        [
            Entry(conversation_id=cid1, date=D(2026, 1, 1), attributes=[{"key": "redness", "severity": 1}]),
            Entry(conversation_id=cid1, date=D(2026, 1, 3), attributes=[{"key": "redness", "severity": 2}]),
            Entry(conversation_id=cid1, date=D(2026, 1, 5), attributes=[{"key": "redness", "severity": 2}]),
        ]
    )
    # A global diet event (Q31) + a conversation-scoped product event.
    session.add(
        TimelineEvent(
            conversation_id=None,
            date=D(2026, 1, 2),
            text="食咗辣底",
            source="user",
        )
    )
    session.add(
        TimelineEvent(
            conversation_id=cid1,
            date=D(2026, 1, 3),  # same day as the entry being deleted later
            text="尋晚冇瞓好",
            source="user",
        )
    )
    session.add(
        TimelineEvent(
            conversation_id=cid1,
            date=D(2026, 1, 4),
            text="開始用：水楊酸 Toner",
            source="user",
        )
    )
    session.add(
        Insight(
            conversation_id=None,  # global fact
            kind="fact",
            tag="user_fact",
            text="對花生敏感",
        )
    )
    session.commit()
    session.close()
    return sf, cid1, cid2


def teardown_env():
    app.dependency_overrides.clear()


def test_summary_merges_global_events_and_insights():
    sf, cid1, cid2 = make_env()
    try:
        client = TestClient(app)
        res = client.get(f"/api/conversations/{cid1}/summary")
        assert res.status_code == 200
        body = res.json()
        scopes = {t["scope"] for t in body["timeline"]}
        assert "global" in scopes and "body_part" in scopes
        texts = {t["text"] for t in body["timeline"]}
        assert "食咗辣底" in texts  # global diet visible here
        # Global insight visible too.
        assert any(i["scope"] == "global" and "花生" in i["text"] for i in body["insights"])
        # Anchors present for the latest entry.
        assert body["anchors"]  # latest entry 1/5 has history
        assert body["anchors"][0]["key"] in ("acne", "oiliness", "redness", "dryness", "pores", "texture")
    finally:
        teardown_env()


def test_summary_second_conversation_sees_global_diet():
    sf, cid1, cid2 = make_env()
    try:
        client = TestClient(app)
        body = client.get(f"/api/conversations/{cid2}/summary").json()
        texts = {t["text"] for t in body["timeline"]}
        assert "食咗辣底" in texts  # body-spanning cause appears on every body part
    finally:
        teardown_env()


def test_correlations_endpoint():
    sf, cid1, cid2 = make_env()
    try:
        client = TestClient(app)
        body = client.get(f"/api/conversations/{cid1}/correlations").json()
        assert "candidates" in body and "note" in body
        # entry_days counts only entries (not events).
        assert body["entry_days"] == 3
        assert 404 == client.get("/api/conversations/nope/correlations").status_code
    finally:
        teardown_env()


def test_delete_entry_removes_entry_photos_and_same_day_conv_events():
    sf, cid1, cid2 = make_env()
    try:
        client = TestClient(app)
        summary = client.get(f"/api/conversations/{cid1}/summary").json()
        target = next(e for e in summary["entries"] if e["date"] == "2026-01-03")
        res = client.delete(f"/api/conversations/{cid1}/entries/{target['id']}")
        assert res.status_code == 200
        after = client.get(f"/api/conversations/{cid1}/summary").json()
        dates = {e["date"] for e in after["entries"]}
        assert "2026-01-03" not in dates
        # Same-day conversation event removed; global diet event + other-day
        # product event kept.
        texts = {t["text"] for t in after["timeline"]}
        assert "食咗辣底" in texts
        assert "開始用：水楊酸 Toner" in texts
        assert "尋晚冇瞓好" not in texts
    finally:
        teardown_env()


def test_edit_entry_note():
    sf, cid1, cid2 = make_env()
    try:
        client = TestClient(app)
        summary = client.get(f"/api/conversations/{cid1}/summary").json()
        target = summary["entries"][0]
        res = client.put(f"/api/conversations/{cid1}/entries/{target['id']}", json={"note": "補記：當日冇瞓好"})
        assert res.status_code == 200
        after = client.get(f"/api/conversations/{cid1}/summary").json()
        edited = next(e for e in after["entries"] if e["id"] == target["id"])
        assert edited["note"] == "補記：當日冇瞓好"
    finally:
        teardown_env()


def test_delete_global_insight_permitted_from_any_conversation():
    sf, cid1, cid2 = make_env()
    try:
        client = TestClient(app)
        summary = client.get(f"/api/conversations/{cid1}/summary").json()
        session = sf()
        gid = (
            session.query(Insight)
            .filter(Insight.conversation_id.is_(None), Insight.text.contains("花生"))
            .first()
        ).id
        session.close()
        res = client.delete(f"/api/conversations/{cid2}/insights/{gid}")
        assert res.status_code == 200
        after = client.get(f"/api/conversations/{cid2}/summary").json()
        assert not any("花生" in i["text"] for i in after["insights"])
    finally:
        teardown_env()
