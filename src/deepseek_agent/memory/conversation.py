from __future__ import annotations

from .base import Message


class ConversationMemory:
    """In-memory sliding-window conversation history."""

    def __init__(self, system_prompt: str = "", max_tokens: int = 8000) -> None:
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self._messages: list[Message] = []
        if system_prompt:
            self._messages.append({"role": "system", "content": system_prompt})

    @property
    def messages(self) -> list[Message]:
        return list(self._messages)

    @property
    def token_count(self) -> int:
        return self._estimate_tokens()

    def add(self, role: str, content: str) -> None:
        self._messages.append({"role": role, "content": content})
        self._trim()

    def add_user(self, content: str) -> None:
        self.add("user", content)

    def add_assistant(self, content: str) -> None:
        self.add("assistant", content)

    def reset(self) -> None:
        self._messages = []
        if self.system_prompt:
            self._messages.append({"role": "system", "content": self.system_prompt})

    def as_list(self, *, include_system: bool = True) -> list[Message]:
        if include_system:
            return list(self._messages)
        return [m for m in self._messages if m["role"] != "system"]

    def _estimate_tokens(self) -> int:
        total = 0
        for m in self._messages:
            total += len(m["content"]) // 3
        return total

    def _trim(self) -> None:
        while self._estimate_tokens() > self.max_tokens:
            for i, m in enumerate(self._messages):
                if m["role"] != "system":
                    self._messages.pop(i)
                    break
            else:
                break
