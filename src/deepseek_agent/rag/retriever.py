from __future__ import annotations

import logging
import os
from typing import Any

import numpy as np

from .embeddings import Embedder, create_embedder
from .loader import Document, load_directory, load_document
from .splitter import RecursiveCharacterSplitter, TextChunk
from .store import VectorEntry, VectorStore

logger = logging.getLogger(__name__)


class Retriever:
    def __init__(self, embedder: Embedder | None = None, embedder_backend: str = "hash",
                 chunk_size: int = 1000, chunk_overlap: int = 200, store_path: str | None = None) -> None:
        self.embedder = embedder or create_embedder(backend=embedder_backend)
        self.splitter = RecursiveCharacterSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.store = VectorStore()
        self.store_path = store_path
        if store_path and os.path.exists(store_path):
            self.store.load(store_path)

    def ingest_file(self, path: str) -> int:
        doc = load_document(path)
        return self._ingest_documents([doc])

    def ingest_directory(self, directory: str, recursive: bool = True) -> int:
        docs = load_directory(directory, recursive=recursive)
        return self._ingest_documents(docs)

    def ingest_text(self, text: str, source: str = "inline", title: str = "") -> int:
        doc = Document(content=text, source=source, title=title)
        return self._ingest_documents([doc])

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        if len(self.store) == 0:
            return []
        q_vec = self.embedder.embed_query(query)
        results = self.store.search(q_vec, top_k=top_k)
        q = q_vec.reshape(1, -1)
        output: list[dict[str, Any]] = []
        for entry in results:
            v = entry.vector.reshape(1, -1)
            sim = float((q @ v.T)[0, 0] / ((np.linalg.norm(q) + 1e-10) * (np.linalg.norm(v) + 1e-10)))
            output.append({
                "text": entry.text, "source": entry.metadata.get("source", ""),
                "title": entry.metadata.get("title", ""), "score": round(sim, 4),
            })
        return output

    def retrieve_context(self, query: str, top_k: int = 5, max_chars: int = 4000) -> str:
        results = self.search(query, top_k=top_k)
        if not results:
            return ""
        parts: list[str] = []
        total = 0
        for r in results:
            snippet = r["text"]
            header = f"[Source: {r['title'] or r['source']}]\n"
            block = header + snippet
            if total + len(block) > max_chars:
                remaining = max_chars - total
                if remaining > len(header) + 50:
                    parts.append(header + snippet[:remaining - len(header)] + "...")
                break
            parts.append(block)
            total += len(block)
        return "\n\n---\n\n".join(parts)

    def save(self) -> None:
        if self.store_path:
            self.store.save(self.store_path)
            logger.info("Vector store saved to %s", self.store_path)

    def clear(self) -> None:
        self.store.clear()

    def _ingest_documents(self, docs: list[Document]) -> int:
        all_chunks: list[TextChunk] = []
        for doc in docs:
            all_chunks.extend(self.splitter.split_document(doc))
        if not all_chunks:
            return 0
        texts = [c.text for c in all_chunks]
        vectors = self.embedder.embed(texts)
        entries = [
            VectorEntry(id=f"{c.source}:{c.chunk_index}", text=c.text, vector=vectors[i],
                        metadata={"source": c.source, "title": c.title, "chunk_index": c.chunk_index})
            for i, c in enumerate(all_chunks)
        ]
        self.store.add_batch(entries)
        if self.store_path:
            self.save()
        logger.info("Ingested %d chunks from %d document(s)", len(entries), len(docs))
        return len(entries)
