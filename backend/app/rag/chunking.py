"""Text chunking for the RAG corpus.

v2: sentence-aware packing with overlap so context at chunk boundaries is not
lost. The `section` argument exists for heading metadata, but no caller passes it
yet (the `chunks.section` column is empty for every row), so section-aware
chunking is plumbing-only until a producer is wired up.
"""
import re

# Sentence boundaries: CJK full-width punctuation, plus ASCII `!`, `?`, `;` and
# `.` — but the ASCII marks only when followed by whitespace, so decimals and
# abbreviations inside a number ("0.5%") are not split. The period was missing
# entirely before, which meant English prose never split at all: the 88% of the
# corpus that comes from English PMC XML was stored in chunks averaging ~2500
# characters (max ~53k) against `chunk_size=500`, far past the embedder's
# 512-token truncation, so most of every English chunk was unreachable.
_SENT_BOUNDARY = re.compile(r"(?<=[。！？；;])\s*|(?<=[.!?])\s+")


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
