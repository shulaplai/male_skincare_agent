"""Text chunking for the RAG corpus.

v1: sentence-aware packing into ~chunk_size chunks. Overlap / sliding-window
chunking is a follow-up once we measure retrieval quality on the real corpus.
"""
import re

_SENT_BOUNDARY = re.compile(r"(?<=[。！？!?；;])")


def chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    sentences = [s.strip() for s in _SENT_BOUNDARY.split(text) if s.strip()]
    chunks: list[str] = []
    current = ""
    for s in sentences:
        if not current:
            current = s
        elif len(current) + 1 + len(s) <= chunk_size:
            current += " " + s
        else:
            chunks.append(current)
            current = s
    if current:
        chunks.append(current)
    return chunks
