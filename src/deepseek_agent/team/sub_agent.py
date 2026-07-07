from __future__ import annotations

import os
from typing import Any

from ..agent import DeepSeekAgent
from ..tools.base import BaseTool, ToolDefinition, ToolParameter


class SubAgent:
    """Lightweight sub-agent for task delegation.

    Wraps a DeepSeekAgent with a specific role.  Call ``.run(task)`` to
    execute a one-shot task and get the result.
    """

    def __init__(
        self,
        role_name: str,
        system_prompt: str,
        model: str | None = None,
    ) -> None:
        self.role_name = role_name
        self.system_prompt = system_prompt
        self.model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")

        self._agent = DeepSeekAgent(
            system_prompt=system_prompt,
            model=self.model,
            enable_tools=False,       # sub-agents get no tools by default (avoid loops)
            enable_rag=False,
            enable_long_term_memory=False,
        )

    def run(self, task: str, context: str = "") -> str:
        """Execute a task and return the result."""
        prompt = task
        if context:
            prompt = f"Context:\n{context}\n\nTask:\n{task}"
        return self._agent.ask(prompt)


class SubAgentTool(BaseTool):
    """Tool that lets the main agent delegate tasks to sub-agents.

    The main agent can call this tool with a role name and task, which
    spawns a temporary sub-agent with the matching skill's system prompt.
    """

    def __init__(self, skill_registry: "SkillRegistry | None" = None) -> None:  # noqa: F821
        self.skill_registry = skill_registry

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="delegate_to_agent",
            description=(
                "Delegate a task to a sub-agent with a specific role. "
                "Use this when a task requires specialized expertise (e.g. code review, research, writing). "
                "Available roles can be listed with the 'list_roles' action."
            ),
            parameters=[
                ToolParameter("action", "string", "Action: 'list_roles' or 'run'",
                              enum=["list_roles", "run"]),
                ToolParameter("role", "string", "Role name for the sub-agent (required for 'run').",
                              required=False),
                ToolParameter("task", "string", "The task description for the sub-agent (required for 'run').",
                              required=False),
                ToolParameter("context", "string", "Additional context/background for the sub-agent.",
                              required=False),
            ],
        )

    def execute(self, action: str = "list_roles", role: str = "", task: str = "",
                context: str = "", **_: Any) -> str:
        if action == "list_roles":
            if self.skill_registry:
                names = self.skill_registry.list_names()
                if names:
                    return "Available roles: " + ", ".join(names)
                return "No custom roles registered. You can use built-in roles: researcher, coder, reviewer, writer."
            return "Available roles: researcher, coder, reviewer, writer."

        if action == "run":
            if not role:
                return "Error: 'role' is required for 'run' action."
            if not task:
                return "Error: 'task' is required for 'run' action."

            # Look up the skill for the role
            system_prompt = ""
            if self.skill_registry:
                skill = self.skill_registry.get(role)
                if skill and skill.system_prompt:
                    system_prompt = skill.system_prompt

            # Built-in fallbacks
            if not system_prompt:
                system_prompt = self._builtin_prompt(role)

            sub = SubAgent(role_name=role, system_prompt=system_prompt)
            result = sub.run(task=task, context=context)
            return f"[Sub-agent '{role}' result]\n{result}"

        return f"Unknown action: {action}"

    # ------------------------------------------------------------------
    @staticmethod
    def _builtin_prompt(role: str) -> str:
        prompts = {
            "researcher": (
                "You are a thorough researcher. When given a topic:\n"
                "1. Identify key aspects and subtopics\n"
                "2. Provide factual, well-organized information\n"
                "3. Cite sources when possible\n"
                "4. Highlight areas of uncertainty\n"
                "Be comprehensive and objective."
            ),
            "coder": (
                "You are an expert software engineer. When given a coding task:\n"
                "1. Write clean, well-structured code with type hints\n"
                "2. Handle edge cases and errors\n"
                "3. Include brief comments for complex logic\n"
                "4. Prefer standard library over third-party dependencies\n"
                "Output only the code with a short explanation."
            ),
            "reviewer": (
                "You are a code reviewer. When reviewing code:\n"
                "1. Identify bugs, edge cases, and security issues\n"
                "2. Suggest performance and readability improvements\n"
                "3. Check for best practices and idiomatic usage\n"
                "Be constructive and specific."
            ),
            "writer": (
                "You are a professional writer and editor. When given a writing task:\n"
                "1. Produce clear, engaging, and well-structured content\n"
                "2. Adapt tone and style to the target audience\n"
                "3. Use proper grammar, spelling, and formatting\n"
                "Deliver polished, publication-ready text."
            ),
        }
        return prompts.get(role, f"You are a helpful assistant specializing in {role}. Be thorough and direct.")
