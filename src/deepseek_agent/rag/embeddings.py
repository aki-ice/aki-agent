from __future__ import annotations

import hashlib
import logging
from typing import Protocol

import numpy as np

logger = logging.getLogger(__name__)


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> np.ndarray: ...
    def embed_query(self, text: str) -> np.ndarray: ...
    @property
    def dimension(self) -> int: ...


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self._model = None
        self._dim = 384

    @property
    def dimension(self) -> int:
        if self._model is not None:
            self._dim = self._model.get_sentence_embedding_dimension()
        return self._dim

    def _lazy_load(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            self._dim = self._model.get_sentence_embedding_dimension()
            logger.info("Loaded embedding model: %s (dim=%d)", self.model_name, self._dim)
        except ImportError:
            raise ImportError(
                "sentence-transformers is not installed. Install it with: pip install sentence-transformers"
            )

    def embed(self, texts: list[str]) -> np.ndarray:
        self._lazy_load()
        embeddings = self._model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return embeddings.astype(np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed([text])[0]


class HashEmbedder:
    def __init__(self, dimension: int = 256) -> None:
        self._dim = dimension

    @property
    def dimension(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.array([self._hash_embed(t) for t in texts], dtype=np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self._hash_embed(text)

    def _hash_embed(self, text: str) -> np.ndarray:
        vec = np.zeros(self._dim, dtype=np.float32)
        for n in (2, 3, 4):
            for i in range(len(text) - n + 1):
                ng = text[i:i + n]
                h = int(hashlib.md5(ng.encode()).hexdigest(), 16)
                idx = h % self._dim
                vec[idx] += 1.0
        norm = np.linalg.norm(vec) + 1e-10
        return vec / norm


def create_embedder(backend: str = "sentence_transformer", **kwargs: object) -> Embedder:
    if backend == "sentence_transformer":
        model_name = str(kwargs.get("model_name", "all-MiniLM-L6-v2"))
        return SentenceTransformerEmbedder(model_name=model_name)
    if backend == "hash":
        dim = int(kwargs.get("dimension", 256))
        return HashEmbedder(dimension=dim)
    raise ValueError(f"Unknown embedder backend: {backend}")
