from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml

PluginType = Literal["skill", "tool"]
PluginSource = Literal["builtin", "imported"]


@dataclass(frozen=True)
class PluginInfo:
    id: str
    type: PluginType
    name: str
    version: str
    description: str
    source: PluginSource
    entry_path: str
    enabled: bool
    trusted: bool
    installed_at: str


class PluginStore:
    BUILTIN_TOOLS = [
        {
            "id": "tool.calculator",
            "type": "tool",
            "name": "calculator",
            "version": "1.0.0",
            "description": "Evaluate mathematical expressions.",
            "source": "builtin",
            "entry_path": "calculator",
            "trusted": 1,
        },
        {
            "id": "tool.datetime",
            "type": "tool",
            "name": "datetime",
            "version": "1.0.0",
            "description": "Get current date/time or compute date offsets.",
            "source": "builtin",
            "entry_path": "datetime",
            "trusted": 1,
        },
        {
            "id": "tool.read_file",
            "type": "tool",
            "name": "read_file",
            "version": "1.0.0",
            "description": "Read text files from the workspace or absolute paths.",
            "source": "builtin",
            "entry_path": "read_file",
            "trusted": 1,
        },
        {
            "id": "tool.list_directory",
            "type": "tool",
            "name": "list_directory",
            "version": "1.0.0",
            "description": "List files and subdirectories.",
            "source": "builtin",
            "entry_path": "list_directory",
            "trusted": 1,
        },
        {
            "id": "tool.write_file",
            "type": "tool",
            "name": "write_file",
            "version": "1.0.0",
            "description": "Create, overwrite, or append text files.",
            "source": "builtin",
            "entry_path": "write_file",
            "trusted": 1,
        },
        {
            "id": "tool.edit_file",
            "type": "tool",
            "name": "edit_file",
            "version": "1.0.0",
            "description": "Edit existing text files by replacing, inserting, deleting, appending, prepending, or replacing line ranges.",
            "source": "builtin",
            "entry_path": "edit_file",
            "trusted": 1,
        },
        {
            "id": "tool.create_directory",
            "type": "tool",
            "name": "create_directory",
            "version": "1.0.0",
            "description": "Create directories including parent directories.",
            "source": "builtin",
            "entry_path": "create_directory",
            "trusted": 1,
        },
        {
            "id": "tool.delete_path",
            "type": "tool",
            "name": "delete_path",
            "version": "1.0.0",
            "description": "Delete files or directories.",
            "source": "builtin",
            "entry_path": "delete_path",
            "trusted": 1,
        },
        {
            "id": "tool.copy_path",
            "type": "tool",
            "name": "copy_path",
            "version": "1.0.0",
            "description": "Copy files or directories.",
            "source": "builtin",
            "entry_path": "copy_path",
            "trusted": 1,
        },
        {
            "id": "tool.move_path",
            "type": "tool",
            "name": "move_path",
            "version": "1.0.0",
            "description": "Move or rename files and directories.",
            "source": "builtin",
            "entry_path": "move_path",
            "trusted": 1,
        },
        {
            "id": "tool.sub_agent",
            "type": "tool",
            "name": "sub_agent",
            "version": "1.0.0",
            "description": "Delegate tasks to specialized sub-agents based on enabled skills or built-in roles.",
            "source": "builtin",
            "entry_path": "sub_agent",
            "trusted": 1,
        },
        {
            "id": "tool.web_search",
            "type": "tool",
            "name": "web_search",
            "version": "1.0.0",
            "description": "Search the web and return result titles, URLs, and snippets.",
            "source": "builtin",
            "entry_path": "web_search",
            "trusted": 1,
        },
        {
            "id": "tool.hot_news",
            "type": "tool",
            "name": "hot_news",
            "version": "1.0.0",
            "description": "Fetch Chinese hot-search ranking lists such as 微博热搜、百度热搜 and 今日热榜.",
            "source": "builtin",
            "entry_path": "hot_news",
            "trusted": 1,
        },
        {
            "id": "tool.web_fetch",
            "type": "tool",
            "name": "web_fetch",
            "version": "1.0.0",
            "description": "Fetch text content from a web page.",
            "source": "builtin",
            "entry_path": "web_fetch",
            "trusted": 1,
        },
    ]

    def __init__(self, db_path: str | Path = "data/agent_workbench.db", builtin_skills_dir: str | Path = "skills") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.builtin_skills_dir = Path(builtin_skills_dir)
        self._init_db()
        self.sync_builtins()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS plugins (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL,
                    entry_path TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    trusted INTEGER NOT NULL DEFAULT 0,
                    installed_at TEXT NOT NULL
                )
                """
            )

    def sync_builtins(self) -> None:
        for plugin in self._scan_builtin_skills():
            self.upsert_plugin(plugin, keep_enabled=True)
        for tool in self.BUILTIN_TOOLS:
            self.upsert_plugin(
                PluginInfo(
                    id=str(tool["id"]),
                    type="tool",
                    name=str(tool["name"]),
                    version=str(tool["version"]),
                    description=str(tool["description"]),
                    source="builtin",
                    entry_path=str(tool["entry_path"]),
                    enabled=True,
                    trusted=True,
                    installed_at=datetime.now().isoformat(timespec="seconds"),
                ),
                keep_enabled=True,
            )

    def _scan_builtin_skills(self) -> list[PluginInfo]:
        plugins: list[PluginInfo] = []
        if not self.builtin_skills_dir.exists():
            return plugins
        for path in sorted(self.builtin_skills_dir.iterdir()):
            if path.suffix.lower() not in {".json", ".yaml", ".yml"}:
                continue
            try:
                data = self._read_skill_meta(path)
            except Exception:
                continue
            name = str(data.get("name") or path.stem)
            metadata = data.get("metadata") or {}
            plugins.append(
                PluginInfo(
                    id=f"skill.{name}",
                    type="skill",
                    name=name,
                    version=str(metadata.get("version", "1.0.0")),
                    description=str(data.get("description", "")),
                    source="builtin",
                    entry_path=str(path.resolve()),
                    enabled=bool(data.get("enabled", True)),
                    trusted=True,
                    installed_at=datetime.now().isoformat(timespec="seconds"),
                )
            )
        return plugins

    def _read_skill_meta(self, path: Path) -> dict:
        if path.suffix.lower() == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def upsert_plugin(self, plugin: PluginInfo, keep_enabled: bool = False) -> None:
        with self._connect() as conn:
            existing = conn.execute("SELECT enabled FROM plugins WHERE id = ?", (plugin.id,)).fetchone()
            enabled = int(existing["enabled"]) if existing and keep_enabled else int(plugin.enabled)
            conn.execute(
                """
                INSERT INTO plugins (
                    id, type, name, version, description, source, entry_path,
                    enabled, trusted, installed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    type = excluded.type,
                    name = excluded.name,
                    version = excluded.version,
                    description = excluded.description,
                    source = excluded.source,
                    entry_path = excluded.entry_path,
                    enabled = ?,
                    trusted = excluded.trusted
                """,
                (
                    plugin.id,
                    plugin.type,
                    plugin.name,
                    plugin.version,
                    plugin.description,
                    plugin.source,
                    plugin.entry_path,
                    enabled,
                    int(plugin.trusted),
                    plugin.installed_at,
                    enabled,
                ),
            )

    def list_plugins(self, plugin_type: PluginType | None = None) -> list[PluginInfo]:
        query = "SELECT * FROM plugins"
        params: tuple[str, ...] = ()
        if plugin_type:
            query += " WHERE type = ?"
            params = (plugin_type,)
        query += " ORDER BY type ASC, source ASC, name ASC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_plugin(row) for row in rows]

    def enabled_skill_paths(self) -> list[str]:
        return [p.entry_path for p in self.list_plugins("skill") if p.enabled and Path(p.entry_path).exists()]

    def enabled_builtin_tool_names(self) -> list[str]:
        return [
            p.entry_path
            for p in self.list_plugins("tool")
            if p.enabled and p.source == "builtin"
        ]

    def enabled_external_tool_paths(self) -> list[str]:
        return [
            p.entry_path
            for p in self.list_plugins("tool")
            if p.enabled and p.source == "imported" and p.trusted and Path(p.entry_path).exists()
        ]

    def set_trusted(self, plugin_id: str, trusted: bool) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE plugins SET trusted = ? WHERE id = ?", (int(trusted), plugin_id))

    def export_config(self, path: str | Path) -> None:
        data = {
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "plugins": [plugin.__dict__ for plugin in self.list_plugins()],
        }
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE plugins SET enabled = ? WHERE id = ?", (int(enabled), plugin_id))

    def delete_plugin(self, plugin_id: str) -> PluginInfo | None:
        plugin = self.get_plugin(plugin_id)
        if not plugin or plugin.source != "imported":
            return None
        with self._connect() as conn:
            conn.execute("DELETE FROM plugins WHERE id = ?", (plugin_id,))
        return plugin

    def get_plugin(self, plugin_id: str) -> PluginInfo | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM plugins WHERE id = ?", (plugin_id,)).fetchone()
        return self._row_to_plugin(row) if row else None

    def _row_to_plugin(self, row: sqlite3.Row) -> PluginInfo:
        return PluginInfo(
            id=str(row["id"]),
            type=row["type"],
            name=str(row["name"]),
            version=str(row["version"]),
            description=str(row["description"]),
            source=row["source"],
            entry_path=str(row["entry_path"]),
            enabled=bool(row["enabled"]),
            trusted=bool(row["trusted"]),
            installed_at=str(row["installed_at"]),
        )
