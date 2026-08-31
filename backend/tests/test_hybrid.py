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
