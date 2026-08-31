from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.rag import DeterministicEmbedder, chunk_text, ingest_text, retrieve


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_chunk_text_sentence_aware():
    text = "油性皮膚容易出油，需要控油清潔。乾性皮膚容易乾燥，需要保濕。"
    chunks = chunk_text(text, chunk_size=20, overlap=0)
    assert len(chunks) >= 2
    assert "".join(chunks).replace(" ", "") == text.replace(" ", "")


def test_chunk_text_with_overlap():
    text = "第一句。第二句。第三句。第四句。第五句。"
    chunks = chunk_text(text, chunk_size=8, overlap=3)
    assert len(chunks) >= 2
    # overlap keeps the boundary word in both neighbouring chunks
    assert any("第二句" in c for c in chunks)


def test_ingest_and_retrieve_roundtrip():
    emb = DeterministicEmbedder()
    session = make_session()
    ingest_text(session, "oily", "油性皮膚容易出油，需要控油清潔，避免油膩產品。", emb)
    ingest_text(session, "dry", "乾性皮膚容易乾燥，需要保濕，使用滋潤產品。", emb)

    results = retrieve(session, "我塊面好油，點控油？", emb, top_k=2)

    assert results[0][0].source == "oily"
    assert results[0][1] > 0.0
    session.close()


def test_empty_ingest_returns_zero():
    emb = DeterministicEmbedder()
    session = make_session()
    assert ingest_text(session, "empty", "", emb) == 0
    session.close()
