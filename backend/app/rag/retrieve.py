"""Retrieval: embed a query and return the most relevant chunks."""
from sqlalchemy.orm import Session

from .embeddings import Embedder
from .vectorstore import search


def retrieve(
    session: Session,
    query: str,
    embedder: Embedder,
    top_k: int = 5,
) -> list[tuple[object, float]]:
    return search(session, embedder.embed(query), top_k)
