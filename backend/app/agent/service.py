"""Service layer: run the agent graph with production dependencies.

Keeps a cached embedder (model load is expensive) and picks the LLM by config
(real adapter if a key is set, FakeLLM otherwise).
"""
from ..db import SessionLocal
from ..rag.embeddings import FastembedEmbedder
from .graph import build_graph
from .llm import get_llm

_embedder: FastembedEmbedder | None = None


def _get_embedder() -> FastembedEmbedder:
    global _embedder
    if _embedder is None:
        _embedder = FastembedEmbedder()
    return _embedder


def run_consult(conversation_id: str, text: str, photo_paths: list[str] | None = None) -> dict:
    graph = build_graph(llm=get_llm(), session_factory=SessionLocal, embedder=_get_embedder())
    return graph.invoke(
        {"conversation_id": conversation_id, "user_text": text, "photo_paths": photo_paths or []}
    )
