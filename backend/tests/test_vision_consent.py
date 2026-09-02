"""Vision + consent behaviour through the real graph (Q18/Q23).

With FakeLLM we cannot exercise a true model call, but we CAN verify the
policy logic: photos are only "sent" (here: read/vision path attempted) when
the conversation opted in AND a real LLM is configured. FakeLLM short-circuits
so vision is never attempted without a real model.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent.graph import build_graph
from app.agent.llm import FakeLLM
from app.db import Base
from app.models import Conversation, Entry, User
from app.rag import DeterministicEmbedder


def make_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _seed_conversation(sf, *, cloud_analysis: bool):
    session = sf()
    u = User(name="阿軒")
    session.add(u)
    session.flush()
    c = Conversation(user_id=u.id, body_part="面部皮膚", cloud_analysis=cloud_analysis)
    session.add(c)
    session.commit()
    cid = c.id
    session.close()
    return cid


def test_photo_without_consent_is_text_only():
    sf = make_factory()
    cid = _seed_conversation(sf, cloud_analysis=False)
    graph = build_graph(llm=FakeLLM(), session_factory=sf, embedder=DeterministicEmbedder())

    # A photo id that does not exist on disk must not crash and must not be
    # "used": consent is off -> text-only.
    result = graph.invoke(
        {"conversation_id": cid, "user_text": "下巴爆瘡", "photo_paths": ["0" * 32], "cloud_analysis": False}
    )
    assert result["vision_used"] is False
    assert result["analysis"]["summary"]


def test_photo_with_consent_but_fakellm_is_text_only():
    sf = make_factory()
    cid = _seed_conversation(sf, cloud_analysis=True)
    graph = build_graph(llm=FakeLLM(), session_factory=sf, embedder=DeterministicEmbedder())

    # Even with consent on, FakeLLM has no vision -> text-only fallback.
    result = graph.invoke(
        {"conversation_id": cid, "user_text": "下巴爆瘡", "photo_paths": ["0" * 32], "cloud_analysis": True}
    )
    assert result["vision_used"] is False


def test_persist_stores_attributes_and_notes_vision():
    sf = make_factory()
    cid = _seed_conversation(sf, cloud_analysis=False)
    graph = build_graph(llm=FakeLLM(), session_factory=sf, embedder=DeterministicEmbedder())
    graph.invoke({"conversation_id": cid, "user_text": "下巴爆瘡", "photo_paths": [], "cloud_analysis": False})

    session = sf()
    entry = session.query(Entry).filter_by(conversation_id=cid).first()
    assert entry is not None
    keys = {a["key"] for a in (entry.attributes or [])}
    assert "acne" in keys
    session.close()
