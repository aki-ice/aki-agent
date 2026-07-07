from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

Message = dict[str, str]


@dataclass
class MemoryEntry:
    """A single entry in long-term memory."""
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    importance: float = 0.5
    created_at: str = ""


class BaseMemory(ABC):
    """Abstract base for all memory backends."""

    @abstractmethod
    def add(self, entry: MemoryEntry) -> None: ...

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[MemoryEntry]: ...

    @abstractmethod
    def clear(self) -> None: ...

    @abstractmethod
    def all(self) -> list[MemoryEntry]: ...
