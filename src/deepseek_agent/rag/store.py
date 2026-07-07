from __future__ import annotations

import os
import pickle
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class VectorEntry:
    id: str
    text: str
    vector: np.ndarray
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_serializable(self) -> dict[str, Any]:
        return {"id": self.id, "text": self.text, "vector": self.vector.tolist(), "metadata": self.metadata}

    @classmethod
    def from_serializable(cls, data: dict[str, Any]) -> "VectorEntry":
        return cls(id=data["id"], text=data["text"], vector=np.array(data["vector"], dtype=np.float32),
                   metadata=data.get("metadata", {}))


class VectorStore:
    def __init__(self) -> None:
        self._entries: list[VectorEntry] = []

    def add(self, entry: VectorEntry) -> None:
        self._entries.append(entry)

    def add_batch(self, entries: list[VectorEntry]) -> None:
        self._entries.extend(entries)

    def search(self, query_vector: np.ndarray, top_k: int = 5) -> list[VectorEntry]:
        if not self._entries:
            return []
        mat = np.stack([e.vector for e in self._entries])
        q = query_vector.reshape(1, -1)
        norms_mat = np.linalg.norm(mat, axis=1, keepdims=True) + 1e-10
        norms_q = np.linalg.norm(q, axis=1, keepdims=True) + 1e-10
        sims = (mat @ q.T).flatten() / (norms_mat.flatten() * norms_q.flatten())
        if top_k >= len(sims):
            indices = list(range(len(sims)))
        else:
            indices = np.argpartition(sims, -top_k)[-top_k:]
            indices = indices[np.argsort(sims[indices])[::-1]]
        return [self._entries[i] for i in indices]

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)

    def save(self, path: str) -> None:
        data = [e.to_serializable() for e in self._entries]
        with open(path, "wb") as fh:
            pickle.dump(data, fh)

    def load(self, path: str) -> None:
        if not os.path.exists(path):
            return
        with open(path, "rb") as fh:
            data = pickle.load(fh)
        self._entries = [VectorEntry.from_serializable(d) for d in data]
