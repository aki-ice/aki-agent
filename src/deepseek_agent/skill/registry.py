from __future__ import annotations

from .base import Skill
from ..tools.base import ToolRegistry


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def unregister(self, name: str) -> None:
        self._skills.pop(name, None)

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def list_names(self) -> list[str]:
        return list(self._skills.keys())

    def list_enabled(self) -> list[Skill]:
        return [s for s in self._skills.values() if s.enabled]

    def enable(self, name: str) -> None:
        skill = self._skills.get(name)
        if skill:
            skill.enabled = True

    def disable(self, name: str) -> None:
        skill = self._skills.get(name)
        if skill:
            skill.enabled = False

    def build_system_prompt(self) -> str:
        parts: list[str] = []
        for skill in self.list_enabled():
            if skill.system_prompt:
                parts.append(f"## Skill: {skill.name}\n{skill.system_prompt}")
        return "\n\n".join(parts)

    def register_tools(self, tool_registry: ToolRegistry) -> None:
        for skill in self.list_enabled():
            for tool in skill.tools:
                tool_registry.register(tool)

    def get_knowledge_files(self) -> list[str]:
        files: list[str] = []
        for skill in self.list_enabled():
            files.extend(skill.knowledge_files)
        return files
