from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class ErrorCategory(str, Enum):
    VALIDATION = "validation"
    NOT_FOUND = "not_found"
    PERMISSION = "permission"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    NETWORK = "network"
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    PROVIDER = "provider"
    TOOL_EXECUTION = "tool_execution"
    INTERNAL = "internal"


@dataclass
class AgentError:
    category: ErrorCategory
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated: bool = False

    def add(self, other: "Usage") -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens or other.prompt_tokens + other.completion_tokens
        self.estimated = self.estimated or other.estimated

    @classmethod
    def from_response(cls, response: Any) -> "Usage":
        value = getattr(response, "usage", None)
        if value is None:
            return cls()
        prompt = int(getattr(value, "prompt_tokens", 0) or 0)
        completion = int(getattr(value, "completion_tokens", 0) or 0)
        total = int(getattr(value, "total_tokens", 0) or prompt + completion)
        return cls(prompt, completion, total, False)


@dataclass
class ToolResult:
    ok: bool
    content: str
    error: AgentError | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0

    def to_model_text(self) -> str:
        if self.ok:
            return self.content
        prefix = self.error.category.value if self.error else "tool_execution"
        return f"Error ({prefix}): {self.content}"


class CancelledError(RuntimeError):
    pass


class CancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise CancelledError("Run cancelled by user")

    def wait(self, timeout: float) -> bool:
        return self._event.wait(timeout)


ApprovalCallback = Callable[[str, dict[str, Any], str], bool]
EventCallback = Callable[[str, dict[str, Any]], None]


@dataclass
class RunContext:
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    session_id: int | None = None
    cancellation: CancellationToken = field(default_factory=CancellationToken)
    usage: Usage = field(default_factory=Usage)
    approval_callback: ApprovalCallback | None = None
    event_callback: EventCallback | None = None
    run_timeout_seconds: int = 900
    tool_timeout_seconds: int = 300
    started_monotonic: float = field(default_factory=time.monotonic)

    def emit(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        if self.event_callback:
            self.event_callback(event_type, payload or {})

    def checkpoint(self) -> None:
        self.cancellation.raise_if_cancelled()
        if time.monotonic() - self.started_monotonic > self.run_timeout_seconds:
            raise TimeoutError(f"Run exceeded {self.run_timeout_seconds} seconds")


class RunStore:
    def __init__(self, db_path: str | Path = "data/agent_workbench.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.recover_interrupted_runs()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=20)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS agent_runs (
                    id TEXT PRIMARY KEY,
                    session_id INTEGER,
                    status TEXT NOT NULL,
                    model TEXT NOT NULL DEFAULT '',
                    user_input TEXT NOT NULL DEFAULT '',
                    output TEXT NOT NULL DEFAULT '',
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    usage_estimated INTEGER NOT NULL DEFAULT 0,
                    error_category TEXT NOT NULL DEFAULT '',
                    error_message TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS run_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tool_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    arguments TEXT NOT NULL DEFAULT '{}',
                    ok INTEGER NOT NULL DEFAULT 0,
                    result TEXT NOT NULL DEFAULT '',
                    error_category TEXT NOT NULL DEFAULT '',
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS approval_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    arguments TEXT NOT NULL DEFAULT '{}',
                    risk TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_run_events_run_id ON run_events(run_id);
                CREATE INDEX IF NOT EXISTS idx_tool_calls_run_id ON tool_calls(run_id);
                """
            )

    def create_run(self, context: RunContext, model: str, user_input: str) -> None:
        now = datetime.now().isoformat(timespec="milliseconds")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO agent_runs (id, session_id, status, model, user_input, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (context.run_id, context.session_id, RunStatus.QUEUED.value, model, user_input, now, now),
            )
        self.set_status(context.run_id, RunStatus.RUNNING)

    def set_status(self, run_id: str, status: RunStatus, *, output: str = "", error: AgentError | None = None, usage: Usage | None = None) -> None:
        now = datetime.now().isoformat(timespec="milliseconds")
        usage = usage or Usage()
        with self._connect() as conn:
            conn.execute(
                """UPDATE agent_runs SET status=?, output=CASE WHEN ? != '' THEN ? ELSE output END,
                prompt_tokens=?, completion_tokens=?, total_tokens=?, usage_estimated=?, error_category=?, error_message=?, updated_at=? WHERE id=?""",
                (status.value, output, output, usage.prompt_tokens, usage.completion_tokens, usage.total_tokens,
                 int(usage.estimated), error.category.value if error else "", error.message if error else "", now, run_id),
            )

    def add_event(self, run_id: str, event_type: str, payload: dict[str, Any] | None = None) -> None:
        now = datetime.now().isoformat(timespec="milliseconds")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO run_events (run_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
                (run_id, event_type, json.dumps(payload or {}, ensure_ascii=False, default=str), now),
            )

    def add_tool_call(self, run_id: str, name: str, arguments: dict[str, Any], result: ToolResult) -> None:
        now = datetime.now().isoformat(timespec="milliseconds")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO tool_calls (run_id, tool_name, arguments, ok, result, error_category, duration_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (run_id, name, json.dumps(self._redact(arguments), ensure_ascii=False, default=str), int(result.ok),
                 result.content, result.error.category.value if result.error else "", result.duration_ms, now),
            )

    def add_approval(self, run_id: str, name: str, arguments: dict[str, Any], risk: str, allowed: bool) -> None:
        now = datetime.now().isoformat(timespec="milliseconds")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO approval_requests (run_id, tool_name, arguments, risk, decision, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, name, json.dumps(self._redact(arguments), ensure_ascii=False, default=str), risk, "allowed" if allowed else "denied", now),
            )

    def list_runs(self, session_id: int | None = None, status: str | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if session_id is not None:
            clauses.append("session_id = ?"); params.append(session_id)
        if status:
            clauses.append("status = ?"); params.append(status)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(f"SELECT * FROM agent_runs{where} ORDER BY created_at DESC LIMIT ? OFFSET ?", (*params, limit, offset)).fetchall()
        return [dict(row) for row in rows]

    def run_events(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM run_events WHERE run_id = ? ORDER BY id", (run_id,)).fetchall()]

    def tool_calls(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM tool_calls WHERE run_id = ? ORDER BY id", (run_id,)).fetchall()]

    def recover_interrupted_runs(self) -> None:
        now = datetime.now().isoformat(timespec="milliseconds")
        with self._connect() as conn:
            conn.execute("UPDATE agent_runs SET status=?, error_category=?, error_message=?, updated_at=? WHERE status IN (?, ?, ?)", (RunStatus.FAILED.value, ErrorCategory.INTERNAL.value, "Application stopped before run completed", now, RunStatus.QUEUED.value, RunStatus.RUNNING.value, RunStatus.WAITING_APPROVAL.value))

    def approval_requests(self, run_id: str | None = None, pending_only: bool = False) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if run_id:
            clauses.append("run_id = ?"); params.append(run_id)
        if pending_only:
            clauses.append("decision = ''")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(f"SELECT * FROM approval_requests{where} ORDER BY id DESC", params).fetchall()]


        now = datetime.now().isoformat(timespec="milliseconds")
        with self._connect() as conn:
            conn.execute(
                "UPDATE agent_runs SET status=?, error_category=?, error_message=?, updated_at=? WHERE status IN (?, ?, ?)",
                (RunStatus.FAILED.value, ErrorCategory.INTERNAL.value, "Application stopped before run completed", now,
                 RunStatus.QUEUED.value, RunStatus.RUNNING.value, RunStatus.WAITING_APPROVAL.value),
            )

    @staticmethod
    def _redact(value: dict[str, Any]) -> dict[str, Any]:
        hidden = {"token", "api_key", "apikey", "authorization", "password", "secret"}
        return {key: "***" if key.lower() in hidden else item for key, item in value.items()}
