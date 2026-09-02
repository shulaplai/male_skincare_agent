from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent.graph import build_graph
from app.agent.llm import FakeLLM
from app.db import Base
from app.models import Conversation, Entry, Insight, User
from app.rag import DeterministicEmbedder, ingest_text


def make_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_agent_end_to_end():
    sf = make_factory()
    embedder = DeterministicEmbedder()

    # Seed a user + conversation + a bit of knowledge.
    session = sf()
    u = User(name="阿軒")
    session.add(u)
    session.flush()
    c = Conversation(user_id=u.id, body_part="面部皮膚", icon="🧔")
    session.add(c)
    session.commit()
    cid = c.id
    ingest_text(session, "oily", "油性皮膚容易出油，需要控油清潔。", embedder)
    session.close()

    graph = build_graph(llm=FakeLLM(), session_factory=sf, embedder=embedder)
    result = graph.invoke({"conversation_id": cid, "user_text": "下巴爆瘡，好油", "photo_paths": []})

    # Structured output flowed through the graph.
    assert result["analysis"]["summary"]
    assert result["advice"]["items"]
    assert result["escalate"] is False
    # Tools ran (knowledge was retrieved).
    assert any(t["tool"] == "search_knowledge" for t in result["tool_results"])

    # Persist wrote an entry + a derived insight.
    session = sf()
    assert session.query(Entry).filter_by(conversation_id=cid).count() == 1
    # Persist wrote one derived insight per rated attribute (Q14/Q47).
    derived = (
        session.query(Insight)
        .filter_by(conversation_id=cid, kind="derived")
        .all()
    )
    assert len(derived) >= 1
    tags = {i.tag for i in derived}
    assert tags & {"acne", "oiliness", "redness"}
    assert all(i.direction in ("problem", "normal") for i in derived)
    session.close()


def test_agent_escalates_on_red_flag():
    sf = make_factory()
    session = sf()
    u = User(name="阿軒")
    session.add(u)
    session.flush()
    c = Conversation(user_id=u.id, body_part="面部皮膚")
    session.add(c)
    session.commit()
    cid = c.id
    session.close()

    graph = build_graph(llm=FakeLLM(), session_factory=sf, embedder=DeterministicEmbedder())
    result = graph.invoke(
        {"conversation_id": cid, "user_text": "塊面突然大面積爛晒，好痛", "photo_paths": []}
    )

    assert result["escalate"] is True
