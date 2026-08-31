"""Hybrid retrieval: semantic (embedding) + keyword (BM25) fused with RRF.

This addresses the "Chinese query flooded by English corpus" problem: keyword
matching rewards chunks that literally contain the query terms, so a Chinese
query surfaces Chinese chunks even when the semantic embedding is dominated by
English academic text.
"""
import re

from rank_bm25 import BM25Okapi

from ..models import Chunk
from .vectorstore import search as semantic_search

SEMANTIC_K = 60
BM25_K = 60
RRF_K = 60

_cache: dict = {"count": -1, "chunks": [], "bm25": None}


def _tokenize(text: str) -> list[str]:
    t = text.lower()
    tokens = re.findall(r"[a-z0-9]+", t)
    zh = re.sub(r"[^\u4e00-\u9fff]", "", t)
    tokens += [zh[i : i + 2] for i in range(len(zh) - 1)]
    return tokens or [t]


def _bm25(session):
    chunks = session.query(Chunk).all()
    count = len(chunks)
    if _cache["count"] != count:
        tokenized = [_tokenize(c.text) for c in chunks]
        _cache.update(count=count, chunks=chunks, bm25=BM25Okapi(tokenized))
    return _cache["bm25"], _cache["chunks"]


def search_hybrid(session, query: str, embedder, top_k: int = 5) -> list[tuple[Chunk, float]]:
    # 1) semantic
    sem = semantic_search(session, embedder.embed(query), top_k=SEMANTIC_K)
    # 2) keyword (BM25)
    bm25, chunks = _bm25(session)
    scores = bm25.get_scores(_tokenize(query))
    bm25_idx = sorted(range(len(chunks)), key=lambda i: -scores[i])[:BM25_K]

    # 3) Reciprocal Rank Fusion
    rrf: dict[str, float] = {}
    for rank, (c, _) in enumerate(sem):
        rrf[c.id] = rrf.get(c.id, 0.0) + 1.0 / (RRF_K + rank + 1)
    for rank, idx in enumerate(bm25_idx):
        c = chunks[idx]
        rrf[c.id] = rrf.get(c.id, 0.0) + 1.0 / (RRF_K + rank + 1)

    best = sorted(rrf.items(), key=lambda x: -x[1])[:top_k]
    id_to_chunk = {c.id: c for c in chunks}
    return [(id_to_chunk[cid], score) for cid, score in best]
