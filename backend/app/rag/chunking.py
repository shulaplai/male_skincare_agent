"""Text chunking for the RAG corpus.

v2: sentence-aware packing with overlap so context at chunk boundaries is not
lost. Section-aware chunking (heading metadata from HTML) is layered in by
callers via the `section` argument.
"""
import re

_SENT_BOUNDARY = re.compile(r"(?<=[。！？!?；;])")


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    if overlap >= chunk_size:
        overlap = max(chunk_size // 4, 0)

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
            tail = current[-overlap:] if overlap else ""
            current = (tail + " " + s).strip() if tail else s
    if current:
        chunks.append(current)
    return chunks
