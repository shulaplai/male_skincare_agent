"""Hybrid retrieval: semantic (embedding) recall, then keyword re-ranking.

Strategy: take the semantic top-N (which already has decent cross-lingual recall),
then boost chunks that literally contain the query's terms. This surfaces
same-language (esp. Chinese) chunks for Chinese queries without letting BM25
flood the result set with irrelevant keyword matches (the RRF-fusion pitfall).
"""
import re

from ..models import Chunk
from .vectorstore import search as semantic_search

RECALL_K = 80
BOOST = 0.18


def _tokenize(text: str) -> list[str]:
    t = text.lower()
    tokens = re.findall(r"[a-z0-9]+", t)
    zh = re.sub(r"[^\u4e00-\u9fff]", "", t)
    tokens += [zh[i : i + 2] for i in range(len(zh) - 1)]
    return tokens


def search_hybrid(session, query: str, embedder, top_k: int = 5) -> list[tuple[Chunk, float]]:
    sem = semantic_search(session, embedder.embed(query), top_k=RECALL_K)
    q_tokens = set(_tokenize(query))
    fused: list[tuple[Chunk, float]] = []
    for c, cos in sem:
        c_tokens = set(_tokenize(c.text))
        overlap = len(q_tokens & c_tokens) / max(len(q_tokens), 1)
        fused.append((c, cos + BOOST * min(overlap, 1.0)))
    fused.sort(key=lambda x: -x[1])
    return fused[:top_k]
