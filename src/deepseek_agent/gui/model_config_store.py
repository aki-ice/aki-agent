from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class ModelConfig:
    id: int
    name: str
    model: str
    base_url: str
    api_key: str
    provider: str
    created_at: str
    updated_at: str


class ModelConfigStore:
    def __init__(self, db_path: str | Path = "data/agent_workbench.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.ensure_defaults()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS model_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    provider TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    api_key TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_model_configs_updated_at ON model_configs(updated_at);
                """
            )

    def ensure_defaults(self) -> None:
        with self._connect() as conn:
            count = int(conn.execute("SELECT COUNT(*) AS c FROM model_configs").fetchone()["c"] or 0)
            if count:
                return
            now = datetime.now().isoformat(timespec="seconds")
            defaults = [
                ("DeepSeek V4 Pro", "DeepSeek", "deepseek-v4-pro", "https://api.deepseek.com"),
                ("DeepSeek Chat", "DeepSeek", "deepseek-chat", "https://api.deepseek.com"),
                ("DeepSeek Reasoner", "DeepSeek", "deepseek-reasoner", "https://api.deepseek.com"),
            ]
            conn.executemany(
                "INSERT INTO model_configs (name, provider, model, base_url, api_key, created_at, updated_at) VALUES (?, ?, ?, ?, '', ?, ?)",
                [(name, provider, model, base_url, now, now) for name, provider, model, base_url in defaults],
            )

    def list_configs(self) -> list[ModelConfig]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM model_configs ORDER BY updated_at DESC, id DESC").fetchall()
        return [self._row_to_config(row) for row in rows]

    def add_config(self, name: str, provider: str, model: str, base_url: str, api_key: str) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO model_configs (name, provider, model, base_url, api_key, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, provider, model, base_url, api_key, now, now),
            )
            return int(cur.lastrowid)

    def delete_config(self, config_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM model_configs WHERE id = ?", (config_id,))

    def get_config(self, config_id: int) -> ModelConfig | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM model_configs WHERE id = ?", (config_id,)).fetchone()
        return self._row_to_config(row) if row else None

    def touch(self, config_id: int) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute("UPDATE model_configs SET updated_at = ? WHERE id = ?", (now, config_id))

    def _row_to_config(self, row: sqlite3.Row) -> ModelConfig:
        return ModelConfig(
            id=int(row["id"]),
            name=str(row["name"]),
            provider=str(row["provider"]),
            model=str(row["model"]),
            base_url=str(row["base_url"]),
            api_key=str(row["api_key"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
