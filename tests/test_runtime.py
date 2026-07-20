from __future__ import annotations

import sqlite3
import time

from deepseek_agent.context import ContextManager
from deepseek_agent.runtime import CancellationToken, ErrorCategory, RunContext, RunStatus, RunStore, Usage
from deepseek_agent.tools.base import BaseTool, ToolDefinition, ToolRegistry


class OkTool(BaseTool):
    @property
    def definition(self):
        return ToolDefinition("ok", "ok")

    def execute(self, **kwargs):
        return "done"


class ErrorTool(BaseTool):
    @property
    def definition(self):
        return ToolDefinition("bad", "bad")

    def execute(self, **kwargs):
        raise FileNotFoundError("missing")


def test_tool_registry_structured_legacy_and_error():
    registry = ToolRegistry()
    registry.register(OkTool())
    registry.register(ErrorTool())
    assert registry.execute_result("ok", {}).ok
    missing = registry.execute_result("bad", {})
    assert not missing.ok
    assert missing.error.category == ErrorCategory.NOT_FOUND
    assert not registry.execute_result("unknown", {}).ok


def test_context_manager_preserves_current_turn_and_compresses_tool():
    manager = ContextManager(max_context_tokens=180, reserved_output_tokens=50)
    messages = [{"role": "system", "content": "policy"}]
    messages.extend({"role": "user" if i % 2 == 0 else "assistant", "content": "old " * 150} for i in range(8))
    messages.append({"role": "user", "content": "CURRENT REQUEST"})
    result = manager.build(messages)
    assert result.messages[0]["role"] == "system"
    assert any("CURRENT REQUEST" in str(item.get("content")) for item in result.messages)
    assert result.dropped_messages > 0


def test_cancellation_token():
    token = CancellationToken()
    assert not token.is_cancelled
    token.cancel()
    assert token.is_cancelled


def test_usage_accumulates():
    usage = Usage()
    usage.add(Usage(10, 4, 14))
    usage.add(Usage(3, 2, 5, True))
    assert (usage.prompt_tokens, usage.completion_tokens, usage.total_tokens) == (13, 6, 19)
    assert usage.estimated


def test_run_store_records_and_recovers(tmp_path):
    db = tmp_path / "runs.db"
    store = RunStore(db)
    context = RunContext(session_id=7)
    store.create_run(context, "model", "hello")
    store.add_event(context.run_id, "model.started", {"x": 1})
    store.set_status(context.run_id, RunStatus.COMPLETED, output="ok", usage=Usage(1, 2, 3))
    with sqlite3.connect(db) as conn:
        status, total = conn.execute("SELECT status, total_tokens FROM agent_runs WHERE id=?", (context.run_id,)).fetchone()
        events = conn.execute("SELECT COUNT(*) FROM run_events WHERE run_id=?", (context.run_id,)).fetchone()[0]
    assert status == "completed"
    assert total == 3
    assert events == 1
