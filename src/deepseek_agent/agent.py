from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from .context import ContextManager
from .memory import ConversationMemory, LongTermMemory, MemoryEntry
from .runtime import RunContext, Usage
from .rag import Retriever
from .skill import SkillRegistry
from .tools import ToolExecutor, ToolRegistry, load_external_tool, register_builtin_tools

Message = dict[str, str]


@dataclass
class DeepSeekAgent:
    # ---- LLM settings ----
    system_prompt: str = "You are a helpful assistant"
    model: str = field(default_factory=lambda: os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"))
    base_url: str = field(default_factory=lambda: os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    reasoning_effort: str = "high"
    thinking_enabled: bool = True
    stream: bool = False

    # ---- Module switches ----
    enable_tools: bool = True
    enable_rag: bool = False
    enable_long_term_memory: bool = False

    # ---- Module configs ----
    max_tool_rounds: int = 5
    rag_top_k: int = 5
    rag_max_context_chars: int = 4000
    memory_db_path: str = "memory.db"
    rag_store_path: str = "rag_store.pkl"
    retriever: Retriever | None = None
    workspace_root: str = "."
    skills_dir: str = ""
    enabled_skill_paths: list[str] = field(default_factory=list)
    enabled_builtin_tools: list[str] | None = None
    enabled_external_tool_paths: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("Set DEEPSEEK_API_KEY environment variable or configure it in .env")

        self.client = OpenAI(api_key=api_key, base_url=self.base_url)

        # ---- sub-systems ----
        self.conv_memory = ConversationMemory(system_prompt=self.system_prompt)
        self.tool_registry = ToolRegistry()
        self.skill_registry = SkillRegistry()
        self.long_term_memory: LongTermMemory | None = None
        if self.retriever is None:
            self.retriever = None

        # ---- initialise sub-systems ----
        if self.enable_tools:
            register_builtin_tools(self.tool_registry, self.workspace_root, self.enabled_builtin_tools)
            from .team import SubAgentTool
            if self.enabled_builtin_tools is None or "sub_agent" in self.enabled_builtin_tools:
                self.tool_registry.register(SubAgentTool(self.skill_registry))

        if self.enable_long_term_memory:
            # share embedder with RAG if both are enabled, otherwise create default
            shared_embedder = self.retriever.embedder if (self.enable_rag and self.retriever) else None
            self.long_term_memory = LongTermMemory(
                self.memory_db_path,
                embedder=shared_embedder,
            )

        if self.enable_rag and self.retriever is None:
            self.retriever = Retriever(
                embedder_backend="hash",
                store_path=self.rag_store_path,
            )

        if self.skills_dir and os.path.isdir(self.skills_dir):
            from .skill import load_skills_from_directory
            for skill in load_skills_from_directory(self.skills_dir):
                self.skill_registry.register(skill)

        if self.enabled_skill_paths:
            from .skill import load_skill
            for skill_path in self.enabled_skill_paths:
                try:
                    self.skill_registry.register(load_skill(skill_path))
                except Exception as exc:
                    print(f"Warning: failed to load enabled skill '{skill_path}': {exc}")

        # Register skill tools
        if self.enable_tools:
            for tool_path in self.enabled_external_tool_paths:
                try:
                    self.tool_registry.register(load_external_tool(tool_path))
                except Exception as exc:
                    print(f"Warning: failed to load external tool '{tool_path}': {exc}")
            self.skill_registry.register_tools(self.tool_registry)

        # Build composite system prompt from skills
        skill_prompt = self.skill_registry.build_system_prompt()
        if skill_prompt:
            self.system_prompt = self.system_prompt + "\n\n" + skill_prompt
            self.conv_memory = ConversationMemory(system_prompt=self.system_prompt)

        self.context_manager = ContextManager(model=self.model)
        self.last_usage = Usage()
        self.tool_executor = ToolExecutor(
            client=self.client, model=self.model,
            registry=self.tool_registry, max_rounds=self.max_tool_rounds,
        )

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def reset(self) -> None:
        self.conv_memory.reset()

    def ask(self, user_input: str, run_context: RunContext | None = None) -> str:
        # ---- RAG: inject relevant context ----
        if self.enable_rag and self.retriever:
            rag_context = self.retriever.retrieve_context(
                user_input, top_k=self.rag_top_k, max_chars=self.rag_max_context_chars
            )
            if rag_context:
                user_input = (
                    "Use the following retrieved knowledge to help answer the question.\n\n"
                    f"[Retrieved Knowledge]\n{rag_context}\n\n"
                    f"[User Question]\n{user_input}"
                )

        # ---- Long-term memory: inject relevant past memories ----
        if self.enable_long_term_memory and self.long_term_memory:
            memories = self.long_term_memory.search(user_input, top_k=3)
            if memories:
                mem_text = "\n".join(f"- {m.content}" for m in memories)
                self.conv_memory.add("system", f"[Relevant past memories]\n{mem_text}")

        self.conv_memory.add_user(user_input)

        # ---- Tool-calling loop ----
        if self.enable_tools and self.tool_registry.tool_names:
            final_text = self.tool_executor.run(
                messages=self.context_manager.build(self.conv_memory.as_list()).messages,
                reasoning_effort=self.reasoning_effort,
                extra_body=self._extra_body(),
            )
        else:
            resp = self.client.chat.completions.create(
                model=self.model, messages=self.conv_memory.as_list(),
                stream=self.stream, reasoning_effort=self.reasoning_effort,
                extra_body=self._extra_body(),
            )
            final_text = resp.choices[0].message.content or ""

        self.conv_memory.add_assistant(final_text)

        # ---- Long-term memory: auto-summarise ----
        if self.enable_long_term_memory and self.long_term_memory:
            self._maybe_summarise()

        return final_text


    def ask_stream(self, user_input: str, run_context: RunContext | None = None):
        if self.enable_rag and self.retriever:
            rag_context = self.retriever.retrieve_context(
                user_input, top_k=self.rag_top_k, max_chars=self.rag_max_context_chars
            )
            if rag_context:
                user_input = (
                    "Use the following retrieved knowledge.\n\n"
                    f"[Retrieved Knowledge]\n{rag_context}\n\n"
                    f"[User Question]\n{user_input}"
                )
        if self.enable_long_term_memory and self.long_term_memory:
            memories = self.long_term_memory.search(user_input, top_k=3)
            if memories:
                mem_text = "\n".join(f"- {m.content}" for m in memories)
                self.conv_memory.add("system", f"[Relevant past memories]\n{mem_text}")
        self.conv_memory.add_user(user_input)
        accumulated = ""
        if self.enable_tools and self.tool_registry.tool_names:
            for chunk in self.tool_executor.run_stream(
                messages=self.context_manager.build(self.conv_memory.as_list()).messages,
                reasoning_effort=self.reasoning_effort,
                extra_body=self._extra_body(),
                run_context=run_context,
            ):
                accumulated += chunk
                yield chunk
        else:
            stream = self.client.chat.completions.create(
                model=self.model, messages=self.conv_memory.as_list(),
                stream=True,
                stream_options={"include_usage": True},
                reasoning_effort=self.reasoning_effort,
                extra_body=self._extra_body(),
            )
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    accumulated += delta.content
                    yield delta.content
        self.conv_memory.add_assistant(accumulated)
        if self.enable_long_term_memory and self.long_term_memory:
            self._maybe_summarise()

    def chat_once(self, user_input: str, history: Iterable[Message] | None = None) -> str:
        messages: list[Message] = [{"role": "system", "content": self.system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_input})
        resp = self.client.chat.completions.create(
            model=self.model, messages=messages, stream=False,
            reasoning_effort=self.reasoning_effort, extra_body=self._extra_body(),
        )
        return resp.choices[0].message.content or ""

    # ------------------------------------------------------------------
    # RAG helpers
    # ------------------------------------------------------------------
    def rag_ingest_file(self, path: str) -> int:
        if not self.retriever:
            raise RuntimeError("RAG is not enabled. Set enable_rag=True.")
        return self.retriever.ingest_file(path)

    def rag_ingest_directory(self, directory: str, recursive: bool = True) -> int:
        if not self.retriever:
            raise RuntimeError("RAG is not enabled. Set enable_rag=True.")
        return self.retriever.ingest_directory(directory, recursive=recursive)

    def rag_ingest_text(self, text: str, source: str = "inline", title: str = "") -> int:
        if not self.retriever:
            raise RuntimeError("RAG is not enabled. Set enable_rag=True.")
        return self.retriever.ingest_text(text, source, title)

    def rag_search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        if not self.retriever:
            raise RuntimeError("RAG is not enabled. Set enable_rag=True.")
        return self.retriever.search(query, top_k)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _extra_body(self) -> dict[str, Any]:
        if not self.thinking_enabled:
            return {}
        return {"thinking": {"type": "enabled"}}

    def _maybe_summarise(self) -> None:
        if not self.long_term_memory:
            return
        msgs = self.conv_memory.as_list(include_system=False)
        if len(msgs) < 6:
            return
        last_user = ""
        last_assistant = ""
        for m in reversed(msgs):
            if m["role"] == "assistant" and not last_assistant:
                last_assistant = m["content"]
            if m["role"] == "user" and not last_user:
                last_user = m["content"]
        if last_user and last_assistant:
            snippet = f"User: {last_user[:200]} | Assistant: {last_assistant[:200]}"
            self.long_term_memory.add(
                MemoryEntry(content=snippet, metadata={"type": "auto_summary"}, importance=0.3)
            )
