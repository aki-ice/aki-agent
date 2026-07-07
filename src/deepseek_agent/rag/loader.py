from __future__ import annotations

import os
import re
from dataclasses import dataclass


@dataclass
class Document:
    content: str
    source: str
    title: str = ""
    page: int = 0


def load_text_file(path: str) -> Document:
    with open(path, encoding="utf-8", errors="replace") as fh:
        content = fh.read()
    return Document(content=content, source=os.path.abspath(path), title=os.path.basename(path))


def load_markdown_file(path: str) -> Document:
    with open(path, encoding="utf-8", errors="replace") as fh:
        raw = fh.read()
    text = re.sub(r"```[\s\S]*?```", " [code block] ", raw)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\(.*?\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    return Document(content=text.strip(), source=os.path.abspath(path), title=os.path.basename(path))


def load_document(path: str) -> Document:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".md", ".markdown"):
        return load_markdown_file(path)
    return load_text_file(path)


def load_directory(directory: str, recursive: bool = True) -> list[Document]:
    docs: list[Document] = []
    supported = {".txt", ".md", ".markdown", ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml"}
    for root, _dirs, files in os.walk(directory):
        for fname in files:
            if os.path.splitext(fname)[1].lower() in supported:
                try:
                    docs.append(load_document(os.path.join(root, fname)))
                except Exception:
                    pass
        if not recursive:
            break
    return docs
