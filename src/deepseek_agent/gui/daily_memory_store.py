from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class DailyMemory:
    day: str
    summary: str
    message_count: int
    session_count: int
    updated_at: str


class DailyMemoryStore:
    def __init__(self, db_path: str | Path = "data/agent_workbench.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_memories (
                    day TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    message_count INTEGER NOT NULL DEFAULT 0,
                    session_count INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_memories_updated_at ON daily_memories(updated_at)")

    def refresh_day(self, day: str | None = None) -> DailyMemory | None:
        day = day or datetime.now().date().isoformat()
        exchanges = self._load_day_exchanges(day)
        if not exchanges:
            return None
        summary = self._build_summary(day, exchanges)
        session_count = len({exchange["session_id"] for exchange in exchanges})
        message_count = len(exchanges) * 2
        updated_at = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO daily_memories (day, summary, message_count, session_count, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(day) DO UPDATE SET
                    summary = excluded.summary,
                    message_count = excluded.message_count,
                    session_count = excluded.session_count,
                    updated_at = excluded.updated_at
                """,
                (day, summary, message_count, session_count, updated_at),
            )
        return DailyMemory(day, summary, message_count, session_count, updated_at)

    def list_memories(self, limit: int = 30) -> list[DailyMemory]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT day, summary, message_count, session_count, updated_at
                FROM daily_memories
                ORDER BY day DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_memory(row) for row in rows]

    def get_memory(self, day: str) -> DailyMemory | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT day, summary, message_count, session_count, updated_at
                FROM daily_memories
                WHERE day = ?
                """,
                (day,),
            ).fetchone()
        return self._row_to_memory(row) if row else None

    def _load_day_exchanges(self, day: str) -> list[dict[str, str | int]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    u.session_id AS session_id,
                    u.content AS question,
                    a.content AS answer,
                    u.created_at AS created_at
                FROM messages u
                JOIN messages a
                    ON a.session_id = u.session_id
                   AND a.role = 'assistant'
                WHERE u.role = 'user'
                  AND substr(u.created_at, 1, 10) = ?
                ORDER BY u.created_at ASC
                """,
                (day,),
            ).fetchall()
        return [
            {
                "session_id": int(row["session_id"]),
                "question": str(row["question"]),
                "answer": str(row["answer"]),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]

    def _build_summary(self, day: str, exchanges: list[dict[str, str | int]]) -> str:
        topics = [self._compact(str(item["question"])) for item in exchanges]
        answer_points = [self._compact(str(item["answer"])) for item in exchanges]
        lines = [
            f"# {day} 对话概要",
            "",
            f"今天共进行了 {len(exchanges)} 轮问答，主要内容如下：",
            "",
            "## 主要问题",
        ]
        for index, topic in enumerate(topics, 1):
            lines.append(f"{index}. {topic}")
        lines.extend(["", "## 回答概要"])
        for index, point in enumerate(answer_points, 1):
            lines.append(f"{index}. {point}")
        lines.extend(["", "## 总结"])
        lines.append(self._overall_summary(topics))
        return "\n".join(lines)

    def _overall_summary(self, topics: list[str]) -> str:
        if not topics:
            return "今天暂无可总结的对话。"
        joined = "；".join(topics[:5])
        if len(topics) > 5:
            joined += f"；以及另外 {len(topics) - 5} 个问题"
        return f"今天的对话主要围绕：{joined}。"

    def _compact(self, text: str, max_len: int = 120) -> str:
        cleaned = " ".join(text.strip().split())
        if not cleaned:
            return "空内容"
        if len(cleaned) <= max_len:
            return cleaned
        return cleaned[:max_len].rstrip() + "..."

    @staticmethod
    def _row_to_memory(row: sqlite3.Row) -> DailyMemory:
        return DailyMemory(
            day=str(row["day"]),
            summary=str(row["summary"]),
            message_count=int(row["message_count"]),
            session_count=int(row["session_count"]),
            updated_at=str(row["updated_at"]),
        )
