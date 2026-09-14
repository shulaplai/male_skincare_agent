"""Service layer: run the agent graph with production dependencies.

Keeps a cached embedder (model load is expensive) and picks the LLM by config
(real adapter if a key is set, FakeLLM otherwise). Reads the conversation's
cloud-analysis consent flag so `analyze` knows whether photos may leave the
machine.

Every consult also appends one JSON line to `settings.run_log_path` (local file,
no photos/keys) containing the per-node trace — that is the post-hoc debug trail
for "the reply looks wrong" (see `scripts/trace_consult.py` for live tracing).
"""
import datetime
import json
import logging
from pathlib import Path

from fastapi import HTTPException

from ..config import settings
from ..db import SessionLocal
from ..models import Conversation
from ..rag.embeddings import FastembedEmbedder
from .graph import build_graph
from .llm import get_llm

logger = logging.getLogger(__name__)

_embedder: FastembedEmbedder | None = None


def _get_embedder() -> FastembedEmbedder:
    global _embedder
    if _embedder is None:
        # Empty cache_dir = library default (a temp dir macOS likes to wipe,
        # which would silently drop us to the 128-dim hashing embedder).
        _embedder = FastembedEmbedder(cache_dir=settings.embedder_cache_dir or None)
    return _embedder


def write_run_log(conversation_id: str, text: str, result: dict) -> None:
    """Append one JSON line per consult. Best-effort: never breaks a consult."""
    if not settings.run_log_enabled:
        return
    try:
        path = Path(settings.run_log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "conversation_id": conversation_id,
            "user_text": text,
            "vision_used": bool(result.get("vision_used")),
            "escalate": bool(result.get("escalate")),
            "tool_calls": (result.get("analysis") or {}).get("tool_calls", []),
            "tools": [
                {
                    "tool": r.get("tool"),
                    "rows": len(r["result"]) if isinstance(r.get("result"), list) else None,
                    "error": r.get("error"),
                }
                for r in result.get("tool_results", [])
            ],
            "trace": result.get("trace", []),
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as e:  # disk full / read-only data dir — logging must not 500
        logger.warning("run log 寫唔入（%s）：%s", settings.run_log_path, e)


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
            "trace": [],
        }
    )
    result["vision_used"] = bool(result.get("vision_used"))
    write_run_log(conversation_id, text, result)
    return result
