from __future__ import annotations

import logging
import os
from collections.abc import Callable, Iterable
from typing import Any

import numpy as np

from .embeddings import Embedder, create_embedder
from .loader import Document, load_directory, load_document
from .splitter import RecursiveCharacterSplitter, TextChunk
from .store import VectorEntry, VectorStore

logger = logging.getLogger(__name__)


class Retriever:
    def __init__(self, embedder: Embedder | None = None, embedder_backend: str = "hash", chunk_size: int = 1000, chunk_overlap: int = 200, store_path: str | None = None) -> None:
        self.embedder = embedder or create_embedder(backend=embedder_backend)
        self.splitter = RecursiveCharacterSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.store = VectorStore()
        self.store_path = store_path
        if store_path and os.path.exists(store_path):
            self.store.load(store_path)

    def ingest_file(self, path: str) -> int:
        return self._ingest_documents([load_document(path)])

    def ingest_files(self, paths: Iterable[str], progress: Callable[[str, int, int], None] | None = None) -> dict[str, Any]:
        added = 0
        failed: list[dict[str, str]] = []
        path_list = list(paths)
        for index, path in enumerate(path_list, start=1):
            if progress:
                progress(path, index, len(path_list))
            try:
                added += self.ingest_file(path)
            except Exception as exc:
                failed.append({"path": path, "error": str(exc)})
        return {"added_chunks": added, "failed": failed, "total": len(path_list)}

    def ingest_directory(self, directory: str, recursive: bool = True, progress: Callable[[str, int, int], None] | None = None) -> int:
        docs = load_directory(directory, recursive=recursive)
        return self._ingest_documents(docs, progress=progress)

    def ingest_text(self, text: str, source: str = "inline", title: str = "") -> int:
        return self._ingest_documents([Document(content=text, source=source, title=title)])

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
            output.append({"id": entry.id, "text": entry.text, "source": entry.metadata.get("source", ""), "title": entry.metadata.get("title", ""), "score": round(sim, 4), "metadata": entry.metadata})
        return output

    def sources(self) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for entry in getattr(self.store, "_entries", []):
            source = str(entry.metadata.get("source", ""))
            item = grouped.setdefault(source, {"source": source, "title": entry.metadata.get("title", ""), "chunks": 0, "metadata": entry.metadata})
            item["chunks"] += 1
        return list(grouped.values())

    def remove_source(self, source: str) -> int:
        entries = getattr(self.store, "_entries", [])
        kept = [entry for entry in entries if entry.metadata.get("source") != source]
        removed = len(entries) - len(kept)
        self.store._entries = kept
        self.save()
        return removed

    def retrieve_context(self, query: str, top_k: int = 5, max_chars: int = 4000) -> str:
        results = self.search(query, top_k=top_k)
        parts: list[str] = []
        total = 0
        for result in results:
            header = f"[Source: {result['title'] or result['source']}]\n"
            block = header + result["text"]
            if total + len(block) > max_chars:
                remaining = max_chars - total
                if remaining > len(header) + 50:
                    parts.append(header + result["text"][:remaining - len(header)] + "...")
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
        self.save()

    def _ingest_documents(self, docs: list[Document], progress: Callable[[str, int, int], None] | None = None) -> int:
        all_chunks: list[TextChunk] = []
        for index, doc in enumerate(docs, start=1):
            if progress:
                progress(doc.source, index, len(docs))
            self.remove_source(doc.source)
            all_chunks.extend(self.splitter.split_document(doc))
        if not all_chunks:
            return 0
        vectors = self.embedder.embed([chunk.text for chunk in all_chunks])
        entries = [VectorEntry(id=f"{chunk.source}:{chunk.chunk_index}", text=chunk.text, vector=vectors[i], metadata={"source": chunk.source, "title": chunk.title, "chunk_index": chunk.chunk_index, **chunk.metadata}) for i, chunk in enumerate(all_chunks)]
        self.store.add_batch(entries)
        self.save()
        logger.info("Ingested %d chunks from %d document(s)", len(entries), len(docs))
        return len(entries)
