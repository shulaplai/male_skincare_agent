"""Embedding abstraction.

The `Embedder` contract is `embed(text) -> list[float]`. `DeterministicEmbedder`
is a dependency-free hashing embedder used for tests and offline development.
`FastembedEmbedder` is the production path (ONNX, no torch) with a graceful
fallback so ingestion never hard-fails without a model.
"""
import hashlib
import logging
import math
import re
from typing import Protocol

logger = logging.getLogger(__name__)


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


class DeterministicEmbedder:
    """Character-bigram hashing embedder (works for zh + en, no deps, no model)."""

    def __init__(self, dim: int = 128):
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        t = re.sub(r"\s+", "", text.lower())
        vec = [0.0] * self.dim
        grams = [t[i : i + 2] for i in range(len(t) - 1)] or [t]
        for g in grams:
            h = int(hashlib.md5(g.encode("utf-8")).hexdigest(), 16)
            vec[h % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec] if norm else vec


class FastembedEmbedder:
    """Real multilingual embeddings via fastembed; falls back to hashing embedder.

    Uses `paraphrase-multilingual-MiniLM-L12-v2` (zh + en) by default (384 dims).
    The fallback is a 128-dim hashing embedder — the two are NOT comparable, so
    falling back is logged loudly instead of being silent (a mixed-dimension
    store would make cosine similarity meaningless).
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        cache_dir: str | None = None,
    ):
        self.model_name = model_name
        self.cache_dir = cache_dir or None
        self._model = None
        self._fallback = DeterministicEmbedder()
        self._warned = False

    def _load(self):
        if self._model is None:
            try:
                from fastembed import TextEmbedding

                kwargs = {"model_name": self.model_name}
                if self.cache_dir:
                    kwargs["cache_dir"] = self.cache_dir
                self._model = TextEmbedding(**kwargs)
            except Exception as e:
                logger.warning(
                    "fastembed model 載入失敗（%s）→ 降級用 %d 維 hash embedder；"
                    "呢個維度同 DB 內可能已有嘅 384 維向量唔可比。",
                    e,
                    len(self._fallback.embed("x")),
                )
                self._model = False
        return self._model

    def embed(self, text: str) -> list[float]:
        model = self._load()
        if model:
            try:
                return [float(x) for x in list(model.embed([text]))[0]]
            except Exception as e:
                if not self._warned:
                    logger.warning("fastembed embed() 出錯（%s）→ 逐次 fallback 去 hash embedder", e)
                    self._warned = True
        return self._fallback.embed(text)
