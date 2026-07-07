from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..tools.base import BaseTool


@dataclass
class Skill:
    name: str
    description: str
    system_prompt: str = ""
    tools: list[BaseTool] = field(default_factory=list)
    knowledge_files: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "description": self.description,
            "system_prompt": self.system_prompt,
            "knowledge_files": self.knowledge_files,
            "metadata": self.metadata, "enabled": self.enabled,
        }
