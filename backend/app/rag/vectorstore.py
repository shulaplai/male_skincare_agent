"""Vector store: SQLite `chunks` table + cosine similarity in Python.

Zero extra infra, fully local-first. For a corpus of tens of thousands of chunks
this is still fast enough; the upgrade path (sqlite-vec / pgvector) is isolated
behind `add_chunks` / `search`, so callers don't change.
"""
import logging
import math
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..models import Chunk

logger = logging.getLogger(__name__)


@dataclass
class ChunkItem:
    text: str
    embedding: list[float]
    source: str = ""
    url: str = ""
    title: str = ""
    section: str = ""


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def existing_dim(session: Session) -> int | None:
    """Embedding dimension of the stored corpus (None when empty).

    Guards the 384-dim real model vs 128-dim hashing fallback mix-up: two
    different dimensions are not comparable, and `_cosine` would silently
    compare only the overlapping prefix.
    """
    row = session.query(Chunk.embedding).first()
    if row is None:
        return None
    emb = row[0]
    return len(emb) if emb else None


def add_chunks(session: Session, items: list[ChunkItem]) -> int:
    if items:
        have = existing_dim(session)
        incoming = len(items[0].embedding)
        if have is not None and have != incoming:
            raise ValueError(
                f"embedding 維度唔一致：DB 現有 {have} 維，今次想寫 {incoming} 維。"
                "（384 = 真 MiniLM；128 = hash fallback）請先清 chunks 重建，"
                "或者修正 embedder 設定，唔好混合兩種向量。"
            )
    for it in items:
        session.add(
            Chunk(
                source=it.source,
                url=it.url,
                title=it.title,
                section=it.section,
                text=it.text,
                embedding=it.embedding,
            )
        )
    session.commit()
    return len(items)


def search(session: Session, embedding: list[float], top_k: int = 5) -> list[tuple[Chunk, float]]:
    chunks = session.query(Chunk).all()
    dim = len(embedding)
    scored = []
    mismatched = 0
    for c in chunks:
        if len(c.embedding or []) != dim:
            mismatched += 1
            continue  # 唔同維度唔可比 —— 跳過，好過靜靜比較前綴
        scored.append((c, _cosine(embedding, c.embedding)))
    if mismatched:
        logger.warning(
            "search: 跳過 %d 條維度唔一致嘅 chunk（query=%d 維）—— 通常代表 ingestion 用過 hash fallback。",
            mismatched,
            dim,
        )
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
