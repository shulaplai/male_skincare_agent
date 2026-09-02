"""Chat-thread persistence through the real graph (Q7/Q35)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent.graph import build_graph
from app.agent.llm import FakeLLM
from app.db import Base
from app.models import ChatMessage, Conversation, User
from app.rag import DeterministicEmbedder


def make_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _seed(sf):
    session = sf()
    u = User(name="阿軒")
    session.add(u)
    session.flush()
    c = Conversation(user_id=u.id, body_part="面部皮膚", cloud_analysis=False)
    session.add(c)
    session.commit()
    cid = c.id
    session.close()
    return cid


def test_consult_persists_user_and_coach_messages():
    sf = make_factory()
    cid = _seed(sf)
    graph = build_graph(llm=FakeLLM(), session_factory=sf, embedder=DeterministicEmbedder())

    graph.invoke({"conversation_id": cid, "user_text": "下巴爆瘡", "photo_paths": [], "cloud_analysis": False})

    session = sf()
    msgs = session.query(ChatMessage).filter_by(conversation_id=cid).order_by(ChatMessage.id).all()
    assert [m.role for m in msgs] == ["user", "coach"]
    assert msgs[0].text == "下巴爆瘡"
    # Coach payload carries what the UI needs to re-render identically.
    assert msgs[1].payload["metrics"]
    assert msgs[1].payload["escalate"] is False
    assert msgs[1].payload["vision_used"] is False
    session.close()


def test_second_consult_sees_first_as_recent_context():
    sf = make_factory()
    cid = _seed(sf)
    graph = build_graph(llm=FakeLLM(), session_factory=sf, embedder=DeterministicEmbedder())

    graph.invoke({"conversation_id": cid, "user_text": "第一句", "photo_paths": [], "cloud_analysis": False})
    res = graph.invoke({"conversation_id": cid, "user_text": "第二句", "photo_paths": [], "cloud_analysis": False})

    # The advise prompt received the previous turn as context (Q39).
    # (FakeLLM ignores the prompt, but we can assert the state carried it.)
    assert any("你：第一句" in m for m in res.get("recent_messages", []))

    session = sf()
    assert session.query(ChatMessage).filter_by(conversation_id=cid).count() == 4
    session.close()
