"""Vector store: SQLite `chunks` table + cosine similarity in Python.

Zero extra infra, fully local-first. For a corpus of tens of thousands of chunks
this is still fast enough; the upgrade path (sqlite-vec / pgvector) is isolated
behind `add_chunks` / `search`, so callers don't change.
"""
import math
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..models import Chunk


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


def add_chunks(session: Session, items: list[ChunkItem]) -> int:
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
    scored = [(c, _cosine(embedding, c.embedding)) for c in chunks]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
