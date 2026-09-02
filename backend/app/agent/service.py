"""Service layer: run the agent graph with production dependencies.

Keeps a cached embedder (model load is expensive) and picks the LLM by config
(real adapter if a key is set, FakeLLM otherwise). Reads the conversation's
cloud-analysis consent flag so `analyze` knows whether photos may leave the
machine.
"""
from fastapi import HTTPException

from ..db import SessionLocal
from ..models import Conversation
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
    session = SessionLocal()
    try:
        conv = session.query(Conversation).filter_by(id=conversation_id).first()
        if conv is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        cloud_analysis = bool(conv.cloud_analysis)
    finally:
        session.close()

    graph = build_graph(
        llm=get_llm("text"),
        vision_llm=get_llm("vision"),
        session_factory=SessionLocal,
        embedder=_get_embedder(),
    )
    result = graph.invoke(
        {
            "conversation_id": conversation_id,
            "user_text": text,
            "photo_paths": photo_paths or [],
            "cloud_analysis": cloud_analysis,
        }
    )
    result["vision_used"] = bool(result.get("vision_used"))
    return result
