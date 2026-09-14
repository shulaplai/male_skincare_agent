from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.rag import DeterministicEmbedder, ingest_text
from app.rag.hybrid import search_hybrid


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_hybrid_roundtrip():
    emb = DeterministicEmbedder()
    s = make_session()
    ingest_text(s, "zh", "水楊酸可以疏通毛孔，幫助改善暗瘡。", emb)
    ingest_text(s, "en", "Salicylic acid helps exfoliate pores for acne.", emb)

    results = search_hybrid(s, "水楊酸疏通毛孔", emb, top_k=2)

    assert len(results) >= 1
    assert results[0][0].source == "zh"
    s.close()


def test_hybrid_respects_top_k():
    emb = DeterministicEmbedder()
    s = make_session()
    for i in range(5):
        ingest_text(s, f"doc{i}", f"護膚內容第{i}段 保濕 防曬 面膜", emb)
    results = search_hybrid(s, "保濕面膜", emb, top_k=3)
    assert len(results) == 3
    s.close()


def test_search_knowledge_routes_through_hybrid(monkeypatch):
    """The runtime tool path must call hybrid, not plain `retrieve()`.

    Reverting `tools.search_knowledge` to pure semantic retrieval is the exact change
    AGENTS.md forbids, and it used to pass every gate: the eval measures `search_hybrid`
    by calling the function directly, so the report kept printing a healthy hybrid
    number for code that no longer ran hybrid. Patching the name the tool module
    actually calls is what makes that revert fail here.
    """
    from app.agent import tools

    calls = []

    def fake_hybrid(session, query, embedder, top_k=3):
        calls.append((query, top_k))
        return []

    monkeypatch.setattr(tools, "search_hybrid", fake_hybrid)
    out = tools.run_tool(
        "search_knowledge",
        {"user_text": "下巴爆瘡點算？", "conversation_id": "c1"},
        make_session(),
        DeterministicEmbedder(),
    )

    assert calls == [("下巴爆瘡點算？", 3)], "search_knowledge no longer routes through search_hybrid"
    assert out["tool"] == "search_knowledge"
    assert out["result"] == []
