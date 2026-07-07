from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any

import numpy as np

from ..rag.embeddings import Embedder, create_embedder
from .base import BaseMemory, MemoryEntry


class LongTermMemory(BaseMemory):
    """SQLite-backed persistent memory with semantic (embedding) search.

    When an embedder is provided, each memory entry is also stored as a
    vector for cosine-similarity retrieval.  Falls back to keyword (LIKE)
    search when no embedder is configured.

    Storage layout (auto-migrated from older versions)::

        id         INTEGER PRIMARY KEY
        content    TEXT    NOT NULL
        metadata   TEXT    DEFAULT '{}'
        importance REAL    DEFAULT 0.5
        created_at TEXT    NOT NULL
        vector     BLOB            -- numpy float32 array, NULL when embedder absent
    """

    def __init__(
        self,
        db_path: str = "memory.db",
        embedder: Embedder | None = None,
        embedder_backend: str = "hash",
    ) -> None:
        self.db_path = db_path
        self.embedder = embedder or create_embedder(backend=embedder_backend)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def add(self, entry: MemoryEntry) -> None:
        if not entry.created_at:
            entry.created_at = time.strftime("%Y-%m-%dT%H:%M:%S")

        vector_blob: bytes | None = None
        if self.embedder is not None:
            vec = self.embedder.embed_query(entry.content)
            vector_blob = vec.astype(np.float32).tobytes()

        self._conn.execute(
            "INSERT INTO memories (content, metadata, importance, created_at, vector) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                entry.content,
                json.dumps(entry.metadata, ensure_ascii=False),
                entry.importance,
                entry.created_at,
                vector_blob,
            ),
        )
        self._conn.commit()

    def search(self, query: str, top_k: int = 5) -> list[MemoryEntry]:
        """Semantic search when embedder is available; keyword fallback otherwise."""
        if self.embedder is not None:
            return self._semantic_search(query, top_k)
        return self._keyword_search(query, top_k)

    def clear(self) -> None:
        self._conn.execute("DELETE FROM memories")
        self._conn.commit()

    def all(self) -> list[MemoryEntry]:
        rows = self._conn.execute(
            "SELECT content, metadata, importance, created_at "
            "FROM memories ORDER BY created_at DESC"
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def summarize_and_store(self, conversation_text: str, importance: float = 0.5) -> None:
        self.add(MemoryEntry(
            content=f"[Conversation Summary] {conversation_text}",
            metadata={"type": "summary"},
            importance=importance,
        ))

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _init_db(self) -> None:
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS memories ("
            "  id         INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  content    TEXT    NOT NULL,"
            "  metadata   TEXT    DEFAULT '{}',"
            "  importance REAL    DEFAULT 0.5,"
            "  created_at TEXT    NOT NULL"
            ")"
        )
        # migration: add vector column if missing (existing DBs)
        try:
            self._conn.execute("SELECT vector FROM memories LIMIT 0")
        except sqlite3.OperationalError:
            self._conn.execute("ALTER TABLE memories ADD COLUMN vector BLOB")
        self._conn.commit()

    def _semantic_search(self, query: str, top_k: int) -> list[MemoryEntry]:
        """Embed query, load all vectors, compute cosine similarity."""
        rows = self._conn.execute(
            "SELECT content, metadata, importance, created_at, vector "
            "FROM memories WHERE vector IS NOT NULL"
        ).fetchall()

        if not rows:
            return []

        q_vec = self.embedder.embed_query(query).reshape(1, -1).astype(np.float32)

        # collect vectors into a matrix
        entries: list[MemoryEntry] = []
        vecs: list[np.ndarray] = []
        for r in rows:
            vecs.append(np.frombuffer(r["vector"], dtype=np.float32))
            entries.append(self._row_to_entry(r))

        mat = np.stack(vecs)                           # (N, D)
        # cosine similarity
        norm_mat = np.linalg.norm(mat, axis=1, keepdims=True) + 1e-10
        norm_q = np.linalg.norm(q_vec, axis=1, keepdims=True) + 1e-10
        sims = (mat @ q_vec.T).flatten() / (norm_mat.flatten() * norm_q.flatten())

        # importance bonus: up to +0.1 boost
        importance = np.array([e.importance for e in entries], dtype=np.float32)
        sims = sims + importance * 0.1

        if top_k >= len(sims):
            indices = list(range(len(sims)))
        else:
            indices = np.argpartition(sims, -top_k)[-top_k:]
            indices = indices[np.argsort(sims[indices])[::-1]]

        return [entries[i] for i in indices]

    def _keyword_search(self, query: str, top_k: int) -> list[MemoryEntry]:
        rows = self._conn.execute(
            "SELECT content, metadata, importance, created_at "
            "FROM memories WHERE content LIKE ? "
            "ORDER BY importance DESC, created_at DESC LIMIT ?",
            (f"%{query}%", top_k),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> MemoryEntry:
        return MemoryEntry(
            content=row["content"],
            metadata=json.loads(row["metadata"]),
            importance=row["importance"],
            created_at=row["created_at"],
        )
