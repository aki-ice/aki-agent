from __future__ import annotations

from deepseek_agent.gui.chat_store import ChatStore
from deepseek_agent.memory import LongTermMemory, MemoryEntry
from deepseek_agent.rag import Retriever
from deepseek_agent.tools.execution import GitTool, RunCodeTool, RunCommandTool


def test_terminal_and_code_execution(tmp_path):
    command = RunCommandTool(str(tmp_path)).execute(command='python -c "print(6 * 7)"')
    assert "exit_code=0" in command and "42" in command
    script = tmp_path / "demo.py"
    script.write_text("print('p1-ok')", encoding="utf-8")
    result = RunCodeTool(str(tmp_path)).execute(path="demo.py")
    assert "exit_code=0" in result and "p1-ok" in result


def test_git_status(tmp_path):
    RunCommandTool(str(tmp_path)).execute(command="git init")
    result = GitTool(str(tmp_path)).execute(action="status")
    assert "exit_code=0" in result


def test_rag_persistence(tmp_path):
    store = tmp_path / "knowledge.pkl"
    retriever = Retriever(store_path=str(store))
    assert retriever.ingest_text("AKI Agent supports Docker sandbox execution", source="manual") == 1
    loaded = Retriever(store_path=str(store))
    results = loaded.search("Docker sandbox", top_k=1)
    assert results and results[0]["source"] == "manual"


def test_long_term_memory_search(tmp_path):
    memory = LongTermMemory(str(tmp_path / "memory.db"))
    memory.add(MemoryEntry("The user prefers Python", importance=0.9))
    assert "Python" in memory.search("preferred language", top_k=1)[0].content


def test_chat_store_fts_migration_and_search(tmp_path):
    store = ChatStore(tmp_path / "chat.db")
    session_id = store.create_session(title="P1")
    store.add_message(session_id, "user", "Docker sandbox network isolation")
    results = store.search("Docker")
    assert results and results[0].session_id == session_id
    reopened = ChatStore(tmp_path / "chat.db")
    assert reopened.search("isolation")
