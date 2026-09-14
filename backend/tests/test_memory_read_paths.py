"""Expiry must be honoured on **read**, not only at write time.

`reconcile` only *extends* expiry when it strengthens a row, so before this the
documented "30 日衰減" described a write-time decision and nothing else: an expired
insight stayed in `/summary` and stayed in the coach's prompt, and because
`strengthen` is the only path that raises confidence, the stale row could end up
outranking the fresh one. Mutation testing found nothing guarding any of it —
deleting the read filter kept the whole suite green — which is what these
assertions exist to fix.
"""
import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent import tools
from app.db import Base, get_session
from app.main import app
from app.models import Conversation, Insight, User
from app.rag import DeterministicEmbedder

EXPIRED = "暗瘡：中等（已過期）"
ACTIVE = "油光：正常（未過期）"


def make_env():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
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
    user = User(name="阿軒")
    session.add(user)
    session.flush()
    conv = Conversation(user_id=user.id, body_part="面部皮膚", cloud_analysis=True)
    session.add(conv)
    session.flush()
    session.add_all(
        [
            Insight(
                conversation_id=conv.id,
                kind="derived",
                tag="acne",
                direction="problem",
                text=EXPIRED,
                confidence=0.85,  # deliberately the *higher* confidence
                expires_at=datetime.datetime(2020, 1, 1),
            ),
            Insight(
                conversation_id=conv.id,
                kind="derived",
                tag="oiliness",
                direction="normal",
                text=ACTIVE,
                confidence=0.6,
                expires_at=datetime.datetime(2999, 1, 1),
            ),
        ]
    )
    session.commit()
    return sf, session, conv.id


def test_summary_hides_expired_insights():
    _sf, session, cid = make_env()
    try:
        body = TestClient(app).get(f"/api/conversations/{cid}/summary").json()
        texts = [i["text"] for i in body["insights"]]
        assert ACTIVE in texts
        assert EXPIRED not in texts, "expired insight is still visible in /summary"
    finally:
        session.close()
        app.dependency_overrides.clear()


def test_coach_memory_tool_hides_expired_insights():
    _sf, session, cid = make_env()
    try:
        out = tools.run_tool(
            "get_skin_profile",
            {"conversation_id": cid},
            session,
            DeterministicEmbedder(),
        )
        texts = [row["text"] for row in out["result"]]
        assert ACTIVE in texts
        assert EXPIRED not in texts, "expired insight still reaches the coach prompt"
    finally:
        session.close()
        app.dependency_overrides.clear()
