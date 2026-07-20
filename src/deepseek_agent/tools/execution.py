from __future__ import annotations

import os
import shlex
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolDefinition, ToolParameter


@dataclass
class ManagedProcess:
    process_id: str
    command: str
    cwd: str
    process: subprocess.Popen[str]


class ProcessManager:
    def __init__(self) -> None:
        self._items: dict[str, ManagedProcess] = {}
        self._lock = threading.Lock()

    def start(self, command: str, cwd: str) -> ManagedProcess:
        process_id = uuid.uuid4().hex[:10]
        process = subprocess.Popen(
            command,
            cwd=cwd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        item = ManagedProcess(process_id, command, cwd, process)
        with self._lock:
            self._items[process_id] = item
        return item

    def get(self, process_id: str) -> ManagedProcess | None:
        with self._lock:
            return self._items.get(process_id)

    def list(self) -> list[ManagedProcess]:
        with self._lock:
            return list(self._items.values())


PROCESS_MANAGER = ProcessManager()


class WorkspaceTool(BaseTool):
    def __init__(self, workspace_root: str = ".") -> None:
        self.workspace_root = os.path.abspath(workspace_root)

    def resolve_cwd(self, cwd: str) -> str:
        target = os.path.abspath(cwd if os.path.isabs(cwd) else os.path.join(self.workspace_root, cwd or "."))
        if os.path.commonpath([self.workspace_root, target]) != self.workspace_root:
            raise PermissionError("Working directory must stay inside the configured workspace")
        if not os.path.isdir(target):
            raise FileNotFoundError(target)
        return target


class RunCommandTool(WorkspaceTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition("run_command", "Run a terminal command inside the workspace. High-risk commands require GUI approval.", [
            ToolParameter("command", "string", "PowerShell/terminal command to run."),
            ToolParameter("cwd", "string", "Workspace-relative working directory.", False),
            ToolParameter("timeout", "integer", "Timeout seconds, default 120.", False),
            ToolParameter("background", "boolean", "Start as managed background process.", False),
        ])

    def execute(self, command: str = "", cwd: str = ".", timeout: int = 120, background: bool = False, **_: Any) -> str:
        if not command.strip():
            return "Error: command is required"
        working = self.resolve_cwd(cwd)
        if background:
            item = PROCESS_MANAGER.start(command, working)
            return f"Process started: id={item.process_id}; pid={item.process.pid}; cwd={working}"
        completed = subprocess.run(command, cwd=working, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=max(1, min(int(timeout), 1800)))
        output = (completed.stdout + completed.stderr).strip()
        if len(output) > 50_000:
            output = output[:50_000] + "\n...[output truncated]"
        return f"exit_code={completed.returncode}\n{output}".strip()


class ProcessTool(BaseTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition("process_control", "List, inspect, read, or terminate managed background processes.", [
            ToolParameter("action", "string", "list/status/read/terminate", enum=["list", "status", "read", "terminate"]),
            ToolParameter("process_id", "string", "Managed process id.", False),
        ])

    def execute(self, action: str = "list", process_id: str = "", **_: Any) -> str:
        if action == "list":
            return "\n".join(f"{item.process_id}: pid={item.process.pid}; state={'running' if item.process.poll() is None else 'exited'}; {item.command}" for item in PROCESS_MANAGER.list()) or "No managed processes"
        item = PROCESS_MANAGER.get(process_id)
        if not item:
            return f"Error: process not found: {process_id}"
        if action == "status":
            return f"pid={item.process.pid}; return_code={item.process.poll()}"
        if action == "terminate":
            item.process.terminate()
            try:
                item.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                item.process.kill()
            return f"Process terminated: {process_id}"
        if action == "read":
            if item.process.poll() is None:
                return "Process is still running; live pipe reads are deferred until it exits."
            output = item.process.stdout.read() if item.process.stdout else ""
            return output[-50_000:] or "No output"
        return f"Error: unknown action: {action}"


class RunCodeTool(WorkspaceTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition("run_code", "Execute a source file using an approved local runtime inside the workspace.", [
            ToolParameter("path", "string", "Workspace-relative source file path."),
            ToolParameter("args", "string", "Command-line arguments.", False),
            ToolParameter("timeout", "integer", "Timeout seconds, default 120.", False),
        ])

    def execute(self, path: str = "", args: str = "", timeout: int = 120, **_: Any) -> str:
        full = os.path.abspath(path if os.path.isabs(path) else os.path.join(self.workspace_root, path))
        if os.path.commonpath([self.workspace_root, full]) != self.workspace_root:
            raise PermissionError("Source file must stay inside workspace")
        if not os.path.isfile(full):
            raise FileNotFoundError(full)
        runtime = {".py": [sys.executable], ".js": ["node"], ".ts": ["npx", "tsx"]}.get(Path(full).suffix.lower())
        if not runtime:
            return "Error: supported source types are .py, .js, and .ts"
        command = runtime + [full] + shlex.split(args, posix=False)
        completed = subprocess.run(command, cwd=os.path.dirname(full), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=max(1, min(int(timeout), 1800)))
        output = (completed.stdout + completed.stderr).strip()
        return f"exit_code={completed.returncode}\n{output[:50000]}".strip()


class GitTool(WorkspaceTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition("git", "Inspect or modify the workspace Git repository.", [
            ToolParameter("action", "string", "status/diff/log/add/commit", enum=["status", "diff", "log", "add", "commit"]),
            ToolParameter("path", "string", "Pathspec for diff/add.", False),
            ToolParameter("message", "string", "Commit message.", False),
        ])

    def execute(self, action: str = "status", path: str = "", message: str = "", **_: Any) -> str:
        commands = {
            "status": ["git", "status", "--short"],
            "diff": ["git", "diff", "--", path or "."],
            "log": ["git", "log", "-10", "--oneline"],
            "add": ["git", "add", "--", path or "."],
            "commit": ["git", "commit", "-m", message],
        }
        if action == "commit" and not message.strip():
            return "Error: commit message is required"
        completed = subprocess.run(commands.get(action, []), cwd=self.workspace_root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        return f"exit_code={completed.returncode}\n{(completed.stdout + completed.stderr).strip()}"


class DockerSandboxTool(WorkspaceTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition("docker_sandbox", "Run a command in a restricted Docker container with the workspace mounted at /workspace.", [
            ToolParameter("command", "string", "Command to run in the container."),
            ToolParameter("image", "string", "Docker image, default python:3.12-slim.", False),
            ToolParameter("timeout", "integer", "Timeout seconds, default 180.", False),
            ToolParameter("network", "boolean", "Allow container networking; default false.", False),
        ])

    def execute(self, command: str = "", image: str = "python:3.12-slim", timeout: int = 180, network: bool = False, **_: Any) -> str:
        if not command.strip():
            return "Error: command is required"
        args = ["docker", "run", "--rm", "--cpus", "1", "--memory", "512m", "--pids-limit", "128", "--security-opt", "no-new-privileges", "-v", f"{self.workspace_root}:/workspace", "-w", "/workspace"]
        if not network:
            args.extend(["--network", "none"])
        args.extend([image, "sh", "-lc", command])
        completed = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=max(1, min(int(timeout), 1800)))
        return f"exit_code={completed.returncode}\n{(completed.stdout + completed.stderr)[:50000].strip()}"
