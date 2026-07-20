from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class DashboardStats:
    sessions: int
    messages: int
    total_tokens: int
    active_days: int
    current_streak: int
    longest_streak: int
    peak_hour: str
    favorite_model: str
    activity: dict[str, int]


class StatsStore:
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
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    model TEXT NOT NULL,
                    message_count INTEGER NOT NULL DEFAULT 0,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    usage_estimated INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON sessions(started_at);
                CREATE INDEX IF NOT EXISTS idx_sessions_model ON sessions(model);
                CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
                """
            )

    def record_exchange(
        self,
        *,
        model: str,
        user_input: str,
        assistant_output: str,
        input_tokens: int,
        output_tokens: int,
    ) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        total_tokens = input_tokens + output_tokens
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO sessions (
                    started_at, ended_at, model, message_count,
                    input_tokens, output_tokens, total_tokens
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (now, now, model, 2, input_tokens, output_tokens, total_tokens),
            )
            session_id = int(cursor.lastrowid)
            conn.execute(
                """
                INSERT INTO messages (
                    session_id, role, content, created_at,
                    input_tokens, output_tokens, total_tokens
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, "user", user_input, now, input_tokens, 0, input_tokens),
            )
            conn.execute(
                """
                INSERT INTO messages (
                    session_id, role, content, created_at,
                    input_tokens, output_tokens, total_tokens
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, "assistant", assistant_output, now, 0, output_tokens, output_tokens),
            )
            return session_id

    def dashboard_stats(self) -> DashboardStats:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS sessions,
                    COALESCE(SUM(message_count), 0) AS messages,
                    COALESCE(SUM(total_tokens), 0) AS total_tokens
                FROM sessions
                """
            ).fetchone()
            favorite = conn.execute(
                """
                SELECT model
                FROM sessions
                GROUP BY model
                ORDER BY COUNT(*) DESC, MAX(started_at) DESC
                LIMIT 1
                """
            ).fetchone()
            peak = conn.execute(
                """
                SELECT strftime('%H', started_at) AS hour
                FROM sessions
                GROUP BY hour
                ORDER BY COUNT(*) DESC, hour ASC
                LIMIT 1
                """
            ).fetchone()
            day_rows = conn.execute(
                """
                SELECT substr(started_at, 1, 10) AS day, COALESCE(SUM(total_tokens), 0) AS tokens
                FROM sessions
                GROUP BY day
                ORDER BY day ASC
                """
            ).fetchall()

        activity = {str(r["day"]): int(r["tokens"] or 0) for r in day_rows}
        active_days = len(activity)
        streak = self._current_streak(set(activity))
        longest = self._longest_streak(set(activity))
        peak_hour = f"{peak['hour']}:00" if peak and peak["hour"] is not None else datetime.now().strftime("%H:00")
        favorite_model = favorite["model"] if favorite and favorite["model"] else "deepseek-v4-pro"

        return DashboardStats(
            sessions=int(row["sessions"] or 0),
            messages=int(row["messages"] or 0),
            total_tokens=int(row["total_tokens"] or 0),
            active_days=active_days,
            current_streak=streak,
            longest_streak=longest,
            peak_hour=peak_hour,
            favorite_model=favorite_model,
            activity=activity,
        )

    def session_totals(self) -> tuple[int, int, int]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS sessions,
                    COALESCE(SUM(input_tokens), 0) AS input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS output_tokens
                FROM sessions
                """
            ).fetchone()
        return int(row["sessions"] or 0), int(row["input_tokens"] or 0), int(row["output_tokens"] or 0)

    @staticmethod
    def _current_streak(days: set[str]) -> int:
        if not days:
            return 0
        today = datetime.now().date()
        streak = 0
        cursor = today
        while cursor.isoformat() in days:
            streak += 1
            cursor -= timedelta(days=1)
        return streak

    @staticmethod
    def _longest_streak(days: set[str]) -> int:
        if not days:
            return 0
        dates = sorted(datetime.fromisoformat(day).date() for day in days)
        longest = 1
        current = 1
        for prev, cur in zip(dates, dates[1:]):
            if cur == prev + timedelta(days=1):
                current += 1
            else:
                longest = max(longest, current)
                current = 1
        return max(longest, current)
