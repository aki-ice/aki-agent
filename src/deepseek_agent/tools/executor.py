from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from .base import ToolRegistry

logger = logging.getLogger(__name__)
Message = dict[str, Any]
FILE_MUTATION_TOOLS = {"write_file", "edit_file", "create_directory", "delete_path", "copy_path", "move_path"}


@dataclass(frozen=True)
class TextToolCall:
    name: str
    arguments: dict[str, Any]


class ToolExecutor:
    def __init__(self, client: OpenAI, model: str, registry: ToolRegistry, max_rounds: int = 5) -> None:
        self.client = client
        self.model = model
        self.registry = registry
        self.max_rounds = max_rounds
        self._last_tool_results: list[tuple[str, str]] = []

    def run(self, messages: list[Message], *, reasoning_effort: str = "medium", extra_body: dict[str, Any] | None = None) -> str:
        tools = self.registry.list_definitions()
        if not tools:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                reasoning_effort=reasoning_effort,
                extra_body=extra_body or {},
            )
            return resp.choices[0].message.content or ""

        for _ in range(self.max_rounds):
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                reasoning_effort=reasoning_effort,
                extra_body=extra_body or {},
            )
            choice = resp.choices[0]

            if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                self._handle_openai_tool_calls(messages, choice.message)
                direct_answer = self._direct_file_mutation_answer() if self._last_user_is_file_only_mutation(messages) else ""
                if direct_answer:
                    return direct_answer
                continue

            content = choice.message.content or ""
            text_calls = self._parse_text_tool_calls(content)
            if text_calls:
                messages.append({"role": "assistant", "content": content})
                self._handle_text_tool_calls(messages, text_calls)
                direct_answer = self._direct_file_mutation_answer() if self._last_user_is_file_only_mutation(messages) else ""
                if direct_answer:
                    return direct_answer
                continue
            if self._last_user_requires_file_mutation(messages) and not self._has_file_mutation_result():
                return "未执行文件操作：没有检测到真实的文件工具调用。请确认 write_file/edit_file 等工具已启用后重试。"
            return self._clean_visible_tool_markup(content)
        return self._finalize_after_max_rounds(messages, reasoning_effort, extra_body)

    def run_stream(self, messages: list[Message], *, reasoning_effort: str = "medium", extra_body: dict[str, Any] | None = None):
        tools = self.registry.list_definitions()
        if not tools:
            yield from self._stream_text(messages, reasoning_effort, extra_body)
            return

        for _ in range(self.max_rounds):
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                reasoning_effort=reasoning_effort,
                extra_body=extra_body or {},
            )
            choice = resp.choices[0]

            if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                self._handle_openai_tool_calls(messages, choice.message)
                direct_answer = self._direct_file_mutation_answer() if self._last_user_is_file_only_mutation(messages) else ""
                if direct_answer:
                    yield direct_answer
                    return
                continue

            content = choice.message.content or ""
            text_calls = self._parse_text_tool_calls(content)
            if text_calls:
                messages.append({"role": "assistant", "content": content})
                self._handle_text_tool_calls(messages, text_calls)
                direct_answer = self._direct_file_mutation_answer() if self._last_user_is_file_only_mutation(messages) else ""
                if direct_answer:
                    yield direct_answer
                    return
                continue

            if self._last_user_requires_file_mutation(messages) and not self._has_file_mutation_result():
                yield "未执行文件操作：没有检测到真实的文件工具调用。请确认 write_file/edit_file 等工具已启用后重试。"
                return
            cleaned = self._clean_visible_tool_markup(content)
            if cleaned:
                yield cleaned
            return
        final_text = self._finalize_after_max_rounds(messages, reasoning_effort, extra_body)
        if final_text:
            yield final_text

    def _handle_openai_tool_calls(self, messages: list[Message], message: Any) -> None:
        self._last_tool_results = []
        messages.append(message.model_dump())
        for tc in message.tool_calls:
            tool_name = tc.function.name
            try:
                tool_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}
            logger.info("Tool call: %s(%s)", tool_name, tool_args)
            result = self.registry.execute(tool_name, tool_args)
            self._last_tool_results.append((tool_name, result))
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    def _handle_text_tool_calls(self, messages: list[Message], calls: list[TextToolCall]) -> None:
        self._last_tool_results = []
        result_blocks: list[str] = []
        for call in calls:
            logger.info("Text tool call: %s(%s)", call.name, call.arguments)
            result = self.registry.execute(call.name, call.arguments)
            self._last_tool_results.append((call.name, result))
            result_blocks.append(f"Tool `{call.name}` result:\n{result}")
        messages.append({
            "role": "user",
            "content": "\n\n".join(result_blocks) + "\n\n请基于工具结果直接回答用户，不要输出工具调用标记。",
        })

    def _direct_file_mutation_answer(self) -> str:
        mutation_results = [(name, result) for name, result in self._last_tool_results if name in FILE_MUTATION_TOOLS]
        if not mutation_results:
            return ""
        lines: list[str] = []
        for name, result in mutation_results:
            lowered = result.lower()
            ok = not any(marker in lowered for marker in ["error", "not found", "no changes made", "permission denied"])
            status = "已执行" if ok else "未成功"
            lines.append(f"{status} `{name}`：{result}")
        return "\n".join(lines)

    def _has_file_mutation_result(self) -> bool:
        return any(name in FILE_MUTATION_TOOLS for name, _ in self._last_tool_results)

    def _last_user_is_file_only_mutation(self, messages: list[Message]) -> bool:
        last_user = self._last_user_text(messages)
        if not last_user or not self._last_user_requires_file_mutation(messages):
            return False
        multi_step_markers = [
            "搜索", "网页", "网上", "根据网上", "根据网页", "生成文档", "生成一份", "md", "markdown", "总结", "资料", "来源",
            "search", "web", "fetch", "markdown", "document", "summary", "summarize", "source",
        ]
        return not any(marker in last_user for marker in multi_step_markers)

    def _last_user_text(self, messages: list[Message]) -> str:
        for message in reversed(messages):
            if message.get("role") == "user":
                content = str(message.get("content", ""))
                if content.startswith("Tool `") or "请基于工具结果" in content:
                    continue
                return content.lower()
        return ""

    def _last_user_requires_file_mutation(self, messages: list[Message]) -> bool:
        last_user = self._last_user_text(messages)
        if not last_user:
            return False
        markers = [
            "创建文件", "新建文件", "写入", "编辑", "修改", "更改", "替换", "删除", "复制", "移动", "重命名", "追加", "插入",
            "create file", "write file", "edit file", "modify file", "replace", "delete file", "copy file", "move file", "rename file", "append",
        ]
        path_like = bool(re.search(r"[a-z]:\\|[a-z]:/|/|\\", last_user, re.IGNORECASE))
        return path_like and any(marker in last_user for marker in markers)

    def _stream_final_from_tool_results(self, messages: list[Message], reasoning_effort: str, extra_body: dict[str, Any] | None):
        direct_answer = self._direct_file_mutation_answer()
        if direct_answer:
            yield direct_answer
            return
        final_messages = messages + [
            {
                "role": "user",
                "content": "请基于以上工具结果直接给出最终回答。要求简洁、结构清晰，不要继续调用工具，不要输出工具调用标记。",
            }
        ]
        yield from self._stream_text(final_messages, reasoning_effort, extra_body)

    def _stream_text(self, messages: list[Message], reasoning_effort: str, extra_body: dict[str, Any] | None):
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
            reasoning_effort=reasoning_effort,
            extra_body=extra_body or {},
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                cleaned = self._clean_visible_tool_markup(delta.content)
                if cleaned:
                    yield cleaned

    def _finalize_after_max_rounds(self, messages: list[Message], reasoning_effort: str, extra_body: dict[str, Any] | None) -> str:
        final_messages = messages + [
            {
                "role": "user",
                "content": "工具调用轮数已用完。请根据已有工具结果给出简洁最终回答；如果信息不足，请说明无法确定。不要输出工具调用标记。",
            }
        ]
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=final_messages,
            reasoning_effort=reasoning_effort,
            extra_body=extra_body or {},
        )
        content = resp.choices[0].message.content or ""
        return self._clean_visible_tool_markup(content) or "工具调用次数已达上限，未能得到可展示的最终回答。"

    def _parse_text_tool_calls(self, content: str) -> list[TextToolCall]:
        normalized = self._normalize_tool_markup(content)
        if "tool_call" not in normalized and "tool_calls" not in normalized:
            return []
        names = [self._normalize_tool_name(name) for name in re.findall(r"invoke\s+name=['\"]([^'\"]+)['\"]", normalized)]
        if not names:
            return []

        args_by_name: dict[str, Any] = {}
        pattern = r"(?:<\|DSML\|\s*)?parameter\s+name=['\"]([^'\"]+)['\"](?:[^>]*)>(.*?)(?:</(?:\|DSML\|\s*)?parameter\s*>)"
        for match in re.finditer(pattern, normalized, re.DOTALL):
            key = match.group(1).strip()
            value = self._coerce_arg(match.group(2).strip())
            args_by_name[key] = value
        return [TextToolCall(name=name, arguments=self._normalize_tool_args(name, dict(args_by_name))) for name in names]

    def _normalize_tool_markup(self, content: str) -> str:
        text = content.replace("｜", "|")
        text = re.sub(r"\|{2,}\s*DSML\s*\|{2,}", "|DSML|", text)
        text = re.sub(r"<\s*\|+\s*DSML\s*\|+", "<|DSML|", text)
        text = re.sub(r"</\s*\|+\s*DSML\s*\|+", "</|DSML|", text)
        text = re.sub(r"\s+>", ">", text)
        return text

    def _normalize_tool_name(self, name: str) -> str:
        aliases = {
            "create_file": "write_file",
            "append_file": "write_file",
            "mkdir": "create_directory",
            "remove_file": "delete_path",
            "delete_file": "delete_path",
            "remove_directory": "delete_path",
            "delete_directory": "delete_path",
            "copy_file": "copy_path",
            "copy_directory": "copy_path",
            "move_file": "move_path",
            "move_directory": "move_path",
            "rename_file": "move_path",
            "edit_text": "edit_file",
            "modify_file": "edit_file",
            "edit_file_text": "edit_file",
            "replace_file_text": "edit_file",
            "insert_file_text": "edit_file",
            "delete_file_text": "edit_file",
        }
        return aliases.get(name.strip(), name.strip())

    def _normalize_tool_args(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name != "edit_file":
            return args
        normalized = dict(args)
        for source in ["find_text", "target_text", "search_text", "old", "before"]:
            if source in normalized and "old_text" not in normalized:
                normalized["old_text"] = normalized[source]
        for source in ["replacement", "replacement_text", "insert_text", "new", "after", "content", "text"]:
            if source in normalized and "new_text" not in normalized:
                normalized["new_text"] = normalized[source]
        if "action" in normalized and "operation" not in normalized:
            normalized["operation"] = normalized["action"]
        if "replace_all_occurrences" in normalized and "replace_all" not in normalized:
            normalized["replace_all"] = normalized["replace_all_occurrences"]
        return normalized

    def _clean_visible_tool_markup(self, content: str) -> str:
        normalized = self._normalize_tool_markup(content)
        if "tool_call" in normalized or "tool_calls" in normalized:
            return ""
        cleaned = re.sub(r"<\/?\|DSML\|[^>]*>", "", normalized)
        cleaned = re.sub(r"<\/?\s*parameter\b[^>]*>", "", cleaned)
        return cleaned.strip()

    def _coerce_arg(self, value: str) -> Any:
        lowered = value.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if lowered == "null":
            return None
        if re.fullmatch(r"-?\d+", value):
            try:
                return int(value)
            except ValueError:
                return value
        if re.fullmatch(r"-?\d+\.\d+", value):
            try:
                return float(value)
            except ValueError:
                return value
        return value
