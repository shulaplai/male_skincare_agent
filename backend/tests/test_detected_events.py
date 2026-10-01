"""AI-extracted self-reported events must survive a reload (issue #22).

The agent proposes diet / product events in `Advice.detected_events`; the user
confirms them with「✅ 記低」before anything is written (`self_report.apply_events`).
Before this, the chips existed only in the browser's live state: a reload lost them,
so the extracted food/product info could never be confirmed — which also starved the
correlation timeline of the data it needs.

Now:
1. `persist` stores `detected_events` in the coach message payload;
2. `GET .../messages` therefore returns them, and `format.ts` renders the chips again;
3. confirming stamps `events_applied` on that message, so a reload does not offer the
   same chip twice (pressing it twice would write the same diet/product twice).
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import crud
from app.agent.graph import build_graph
from app.agent.schemas import Advice, DetectedEvent, SkinAnalysis
from app.db import Base
from app.models import ChatMessage, Conversation, User
from app.rag import DeterministicEmbedder


@pytest.fixture()
def sf(tmp_path):
    # 一定要用**檔案** DB：TestClient 喺另一條 thread 行 app，`:memory:` 每個
    # connection 都會開一個新空 DB（實測 `no such table: conversations`）。
    engine = create_engine(f"sqlite:///{tmp_path / 'events.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def seed(sf) -> str:
    s = sf()
    u = User(name="阿軒")
    s.add(u)
    s.flush()
    c = Conversation(user_id=u.id, body_part="面部皮膚", cloud_analysis=True)
    s.add(c)
    s.commit()
    cid = c.id
    s.close()
    return cid


class StubLLM:
    """Reports skin + one diet event + one product event, like a real 「食咗辣、開始用酸」 turn."""

    def structured(self, system, user, schema):
        if schema is SkinAnalysis:
            return SkinAnalysis(
                observes_skin=True,
                summary="下巴一粒",
                attributes=[{"key": "acne", "severity": 2, "note": ""}],
            )
        return Advice(
            reply="記低咗你食咗辣同開始用水楊酸。",
            items=["留意兩日內有冇爆瘡"],
            disclaimer="僅供參考",
            escalate=False,
            detected_events=[
                DetectedEvent(type="diet", text="食咗辣底打邊爐", tags=["spicy"]),
                DetectedEvent(type="product_start", text="開始用水楊酸 toner", product_name="水楊酸 toner"),
            ],
        )

    def structured_vision(self, system, user, schema, images):
        return self.structured(system, user, schema)


def consult(sf, cid, text="今日食咗辣，開始用支水楊酸 toner"):
    g = build_graph(
        llm=StubLLM(), vision_llm=StubLLM(), session_factory=sf, embedder=DeterministicEmbedder()
    )
    return g.invoke(
        {"conversation_id": cid, "user_text": text, "photo_paths": [], "cloud_analysis": True, "trace": []}
    )


def test_persist_stores_detected_events_in_the_coach_payload(sf):
    cid = seed(sf)
    consult(sf, cid)

    s = sf()
    try:
        coach = (
            s.query(ChatMessage)
            .filter_by(conversation_id=cid, role="coach")
            .order_by(ChatMessage.id.desc())
            .first()
        )
        assert coach is not None
        events = coach.payload.get("detected_events")
        assert [e["type"] for e in events] == ["diet", "product_start"]
        assert events[0]["tags"] == ["spicy"]
        assert events[1]["product_name"] == "水楊酸 toner"
        assert "events_applied" not in coach.payload
    finally:
        s.close()


def test_messages_endpoint_returns_the_events_for_reload(sf):
    from fastapi.testclient import TestClient

    from app.db import get_session
    from app.main import app

    cid = seed(sf)
    consult(sf, cid)

    def override():
        s = sf()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = override
    try:
        with TestClient(app) as client:
            msgs = client.get(f"/api/conversations/{cid}/messages").json()
            coach = [m for m in msgs if m["role"] == "coach"][-1]
            assert len(coach["payload"]["detected_events"]) == 2

            # 用戶撳「✅ 記低」（session 內新訊息冇 DB id → 靠事件內容配對）
            r = client.post(
                f"/api/conversations/{cid}/events",
                json={"events": coach["payload"]["detected_events"]},
            ).json()
            assert r["written"] == 2, "diet + product 兩條都要寫入"
            assert r["events_applied_on"] is not None

            # reload 之後唔會再出同一個 chip
            coach2 = [m for m in client.get(f"/api/conversations/{cid}/messages").json() if m["role"] == "coach"][-1]
            assert coach2["payload"]["events_applied"] is True
    finally:
        app.dependency_overrides.clear()


def test_confirming_by_message_id_marks_exactly_that_message(sf):
    from fastapi.testclient import TestClient

    from app.db import get_session
    from app.main import app

    cid = seed(sf)
    consult(sf, cid)

    def override():
        s = sf()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = override
    try:
        with TestClient(app) as client:
            coach_ids = [
                m["id"] for m in client.get(f"/api/conversations/{cid}/messages").json() if m["role"] == "coach"
            ]
            first = coach_ids[0]
            r = client.post(
                f"/api/conversations/{cid}/events",
                json={
                    "events": [{"type": "diet", "text": "食咗辣底打邊爐", "tags": ["spicy"]}],
                    "message_id": first,
                },
            ).json()
            assert r["events_applied_on"] == first
            msgs = client.get(f"/api/conversations/{cid}/messages").json()
            assert [m for m in msgs if m["id"] == first][0]["payload"]["events_applied"] is True
    finally:
        app.dependency_overrides.clear()


def test_no_match_leaves_payloads_untouched(sf):
    """冇一條 message 出過嗰個 chip（例如用戶自己打）→ 冇 message 需要標記，唔可以亂標。"""
    from fastapi.testclient import TestClient

    from app.db import get_session
    from app.main import app

    cid = seed(sf)
    consult(sf, cid)

    def override():
        s = sf()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = override
    try:
        with TestClient(app) as client:
            r = client.post(
                f"/api/conversations/{cid}/events",
                json={"events": [{"type": "diet", "text": "飲咗咖啡", "tags": []}]},
            ).json()
            assert r["written"] == 1
            assert r["events_applied_on"] is None
            for m in client.get(f"/api/conversations/{cid}/messages").json():
                assert not (m["payload"] or {}).get("events_applied")
    finally:
        app.dependency_overrides.clear()


def test_consent_default_does_not_block_stub_consult(sf):
    """（守門）self-host 預設同意已給：stub consult 唔會因為 consent gate 而變文字-only。"""
    s = sf()
    try:
        assert crud.get_or_create_default_user(s).photo_cloud_consent is True
    finally:
        s.close()
