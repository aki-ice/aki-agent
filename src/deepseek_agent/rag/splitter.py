from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TextChunk:
    text: str
    source: str
    chunk_index: int
    title: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


class RecursiveCharacterSplitter:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200, separators: list[str] | None = None) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]

    def split(self, text: str) -> list[str]:
        return self._split_recursive(text, self.separators)

    def split_document(self, document: "Document") -> list[TextChunk]:  # noqa: F821
        chunks = self.split(document.content)
        return [
            TextChunk(
                text=chunk,
                source=document.source,
                chunk_index=i,
                title=document.title,
                metadata={**document.metadata, "page": document.page},
            )
            for i, chunk in enumerate(chunks)
        ]

    def _split_recursive(self, text: str, separators: list[str]) -> list[str]:
        final: list[str] = []
        separator = separators[-1]
        for sep in separators:
            if sep == "" or sep in text:
                separator = sep
                break
        if separator == "":
            step = max(1, self.chunk_size - self.chunk_overlap)
            return [text[i:i + self.chunk_size] for i in range(0, len(text), step) if text[i:i + self.chunk_size]]

        splits = text.split(separator)
        current = ""
        for part in splits:
            if len(current) + len(part) + len(separator) <= self.chunk_size:
                current = (current + separator + part) if current else part
            else:
                if current:
                    final.append(current)
                if len(part) > self.chunk_size:
                    idx = separators.index(separator)
                    final.extend(self._split_recursive(part, separators[idx + 1:]))
                    current = ""
                else:
                    current = part
        if current:
            final.append(current)
        return final
