"""Embedding abstraction.

The `Embedder` contract is `embed(text) -> list[float]`. `DeterministicEmbedder`
is a dependency-free hashing embedder used for tests and offline development.
`FastembedEmbedder` is the production path (ONNX, no torch) with a graceful
fallback so ingestion never hard-fails without a model.
"""
import hashlib
import math
import re
from typing import Protocol


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

    Uses `paraphrase-multilingual-MiniLM-L12-v2` (zh + en) by default.
    """

    def __init__(self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        self.model_name = model_name
        self._model = None
        self._fallback = DeterministicEmbedder()

    def _load(self):
        if self._model is None:
            try:
                from fastembed import TextEmbedding

                self._model = TextEmbedding(model_name=self.model_name)
            except Exception:
                self._model = False
        return self._model

    def embed(self, text: str) -> list[float]:
        model = self._load()
        if model:
            try:
                return [float(x) for x in list(model.embed([text]))[0]]
            except Exception:
                pass
        return self._fallback.embed(text)
