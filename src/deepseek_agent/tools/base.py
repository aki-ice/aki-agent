from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..runtime import AgentError, ErrorCategory, ToolResult


@dataclass
class ToolParameter:
    name: str
    type: str
    description: str
    required: bool = True
    enum: list[str] | None = None


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)

    def to_openai_schema(self) -> dict[str, Any]:
        properties: dict[str, Any] = {}
        required: list[str] = []
        for parameter in self.parameters:
            prop: dict[str, Any] = {"type": parameter.type, "description": parameter.description}
            if parameter.enum:
                prop["enum"] = parameter.enum
            properties[parameter.name] = prop
            if parameter.required:
                required.append(parameter.name)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {"type": "object", "properties": properties, "required": required},
            },
        }


class BaseTool(ABC):
    @property
    @abstractmethod
    def definition(self) -> ToolDefinition: ...

    @abstractmethod
    def execute(self, **kwargs: Any) -> str | ToolResult: ...


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.definition.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list_definitions(self) -> list[dict[str, Any]]:
        return [tool.definition.to_openai_schema() for tool in self._tools.values()]

    def execute_result(self, name: str, arguments: str | dict[str, Any]) -> ToolResult:
        started = time.monotonic()
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(False, f"unknown tool '{name}'", AgentError(ErrorCategory.NOT_FOUND, "unknown_tool", f"Unknown tool '{name}'"))
        try:
            parsed = json.loads(arguments) if isinstance(arguments, str) else arguments
            if not isinstance(parsed, dict):
                raise ValueError("Tool arguments must be a JSON object")
            raw = tool.execute(**parsed)
            result = raw if isinstance(raw, ToolResult) else self._wrap_legacy_result(str(raw))
        except json.JSONDecodeError as exc:
            result = ToolResult(False, str(exc), AgentError(ErrorCategory.VALIDATION, "invalid_json", str(exc)))
        except (TypeError, ValueError) as exc:
            result = ToolResult(False, str(exc), AgentError(ErrorCategory.VALIDATION, "invalid_arguments", str(exc)))
        except PermissionError as exc:
            result = ToolResult(False, str(exc), AgentError(ErrorCategory.PERMISSION, "permission_denied", str(exc)))
        except FileNotFoundError as exc:
            result = ToolResult(False, str(exc), AgentError(ErrorCategory.NOT_FOUND, "not_found", str(exc)))
        except TimeoutError as exc:
            result = ToolResult(False, str(exc), AgentError(ErrorCategory.TIMEOUT, "tool_timeout", str(exc), True))
        except Exception as exc:
            result = ToolResult(False, str(exc), AgentError(ErrorCategory.TOOL_EXECUTION, "tool_exception", str(exc)))
        result.duration_ms = max(result.duration_ms, int((time.monotonic() - started) * 1000))
        return result

    def execute(self, name: str, arguments: str | dict[str, Any]) -> str:
        return self.execute_result(name, arguments).to_model_text()

    @staticmethod
    def _wrap_legacy_result(content: str) -> ToolResult:
        lowered = content.strip().lower()
        markers = ("error", "not found", "permission denied", "no changes made", "failed", "失败", "错误")
        if not any(marker in lowered for marker in markers):
            return ToolResult(True, content)
        category = ErrorCategory.TOOL_EXECUTION
        if "not found" in lowered:
            category = ErrorCategory.NOT_FOUND
        elif "permission" in lowered:
            category = ErrorCategory.PERMISSION
        elif "timeout" in lowered:
            category = ErrorCategory.TIMEOUT
        elif "token" in lowered or "authentication" in lowered or "unauthorized" in lowered:
            category = ErrorCategory.AUTHENTICATION
        elif "required" in lowered or "invalid" in lowered:
            category = ErrorCategory.VALIDATION
        return ToolResult(False, content, AgentError(category, "legacy_tool_error", content, category == ErrorCategory.TIMEOUT))

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())
