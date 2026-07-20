from __future__ import annotations

from dataclasses import dataclass
from typing import Any

Message = dict[str, Any]


@dataclass
class ContextBuildResult:
    messages: list[Message]
    estimated_tokens: int
    dropped_messages: int = 0
    compressed_tool_results: int = 0


class TokenEstimator:
    def __init__(self, model: str = "") -> None:
        self.model = model
        self._encoder = None
        try:
            import tiktoken
            try:
                self._encoder = tiktoken.encoding_for_model(model)
            except KeyError:
                self._encoder = tiktoken.get_encoding("cl100k_base")
        except ImportError:
            self._encoder = None

    def count_text(self, text: str) -> int:
        if self._encoder is not None:
            return len(self._encoder.encode(text))
        ascii_count = sum(1 for char in text if ord(char) < 128)
        non_ascii = len(text) - ascii_count
        return max(1, ascii_count // 4 + non_ascii)

    def count_messages(self, messages: list[Message]) -> int:
        return sum(4 + self.count_text(str(message.get("content", ""))) for message in messages) + 2


class ContextManager:
    def __init__(self, model: str = "", max_context_tokens: int = 32_000, reserved_output_tokens: int = 4_000) -> None:
        self.estimator = TokenEstimator(model)
        self.max_context_tokens = max_context_tokens
        self.reserved_output_tokens = reserved_output_tokens

    @property
    def input_budget(self) -> int:
        return max(1_000, self.max_context_tokens - self.reserved_output_tokens)

    def build(self, messages: list[Message]) -> ContextBuildResult:
        copied = [dict(message) for message in messages]
        compressed = self._compress_tool_results(copied)
        tokens = self.estimator.count_messages(copied)
        if tokens <= self.input_budget:
            return ContextBuildResult(copied, tokens, compressed_tool_results=compressed)

        system = [message for message in copied if message.get("role") == "system"]
        non_system = [message for message in copied if message.get("role") != "system"]
        current_start = self._current_turn_start(non_system)
        current_turn = non_system[current_start:]
        older = non_system[:current_start]
        selected = list(current_turn)

        for message in reversed(older):
            candidate = system + [message] + selected
            if self.estimator.count_messages(candidate) > self.input_budget:
                break
            selected.insert(0, message)

        dropped = len(non_system) - len(selected)
        if dropped:
            summary = self._summary_message(older[:dropped])
            if summary:
                candidate = system + [summary] + selected
                if self.estimator.count_messages(candidate) <= self.input_budget:
                    selected.insert(0, summary)

        result = system + selected
        while self.estimator.count_messages(result) > self.input_budget and len(selected) > len(current_turn):
            selected.pop(0)
            result = system + selected
        return ContextBuildResult(result, self.estimator.count_messages(result), dropped, compressed)

    def _compress_tool_results(self, messages: list[Message], max_chars: int = 8_000) -> int:
        count = 0
        for message in messages:
            if message.get("role") != "tool":
                continue
            content = str(message.get("content", ""))
            if len(content) <= max_chars:
                continue
            message["content"] = content[:max_chars] + f"\n...[tool result truncated; original chars={len(content)}]"
            count += 1
        return count

    @staticmethod
    def _current_turn_start(messages: list[Message]) -> int:
        for index in range(len(messages) - 1, -1, -1):
            if messages[index].get("role") == "user":
                return index
        return max(0, len(messages) - 2)

    @staticmethod
    def _summary_message(messages: list[Message], max_chars: int = 4_000) -> Message | None:
        if not messages:
            return None
        snippets: list[str] = []
        used = 0
        for message in messages[-12:]:
            content = " ".join(str(message.get("content", "")).split())
            snippet = f"{message.get('role', 'unknown')}: {content[:500]}"
            if used + len(snippet) > max_chars:
                break
            snippets.append(snippet)
            used += len(snippet)
        if not snippets:
            return None
        return {"role": "system", "content": "[Compressed earlier conversation]\n" + "\n".join(snippets)}
