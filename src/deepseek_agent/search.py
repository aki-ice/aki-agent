from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class SearchHit:
    source: str
    text: str
    score: float
    metadata: dict[str, object]


def _ngrams(text: str, width: int = 2) -> set[str]:
    compact = re.sub(r"\s+", "", text.lower())
    if len(compact) <= width:
        return {compact} if compact else set()
    return {compact[index:index + width] for index in range(len(compact) - width + 1)}


class NgramIndex:
    def __init__(self, width: int = 2) -> None:
        self.width = width
        self._documents: dict[str, tuple[str, dict[str, object]]] = {}
        self._index: dict[str, set[str]] = {}

    def add(self, source: str, text: str, metadata: dict[str, object] | None = None) -> None:
        self.remove(source)
        self._documents[source] = (text, metadata or {})
        for gram in _ngrams(text, self.width):
            self._index.setdefault(gram, set()).add(source)

    def remove(self, source: str) -> None:
        self._documents.pop(source, None)
        for sources in self._index.values():
            sources.discard(source)

    def search(self, query: str, top_k: int = 10) -> list[SearchHit]:
        grams = _ngrams(query, self.width)
        candidates = set().union(*(self._index.get(gram, set()) for gram in grams)) if grams else set()
        scored: list[SearchHit] = []
        for source in candidates:
            text, metadata = self._documents[source]
            document_grams = _ngrams(text, self.width)
            score = len(grams & document_grams) / max(1, len(grams))
            scored.append(SearchHit(source, text, score, metadata))
        return sorted(scored, key=lambda hit: hit.score, reverse=True)[:top_k]

    def __len__(self) -> int:
        return len(self._documents)


class SearchService:
    def __init__(self, retriever=None, chat_store=None) -> None:
        self.retriever = retriever
        self.chat_store = chat_store
        self.ngram = NgramIndex()

    def index_text(self, source: str, text: str, metadata: dict[str, object] | None = None) -> None:
        self.ngram.add(source, text, metadata)

    def search(self, query: str, top_k: int = 10) -> list[SearchHit]:
        hits = list(self.ngram.search(query, top_k))
        if self.retriever:
            hits.extend(SearchHit(str(item["source"]), str(item["text"]), float(item["score"]), item.get("metadata", {})) for item in self.retriever.search(query, top_k=top_k))
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:top_k]
