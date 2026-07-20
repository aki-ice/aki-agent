from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class ChatSearchResult:
    session_id: int
    session_title: str
    role: str
    snippet: str
    created_at: str


@dataclass(frozen=True)
class ChatSession:
    id: int
    title: str
    created_at: str
    updated_at: str
    message_count: int


class ChatStore:
    def __init__(self, db_path: str | Path = "data/agent_workbench.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._init_fts()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    model TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated_at ON chat_sessions(updated_at);
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
                """
            )

    def _init_fts(self) -> None:
        with self._connect() as conn:
            try:
                conn.executescript("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS chat_messages_fts USING fts5(content, role UNINDEXED, session_id UNINDEXED, content='chat_messages', content_rowid='id');
                    CREATE TRIGGER IF NOT EXISTS chat_messages_ai AFTER INSERT ON chat_messages BEGIN INSERT INTO chat_messages_fts(rowid, content, role, session_id) VALUES (new.id, new.content, new.role, new.session_id); END;
                    CREATE TRIGGER IF NOT EXISTS chat_messages_ad AFTER DELETE ON chat_messages BEGIN INSERT INTO chat_messages_fts(chat_messages_fts, rowid, content, role, session_id) VALUES ('delete', old.id, old.content, old.role, old.session_id); END;
                    INSERT INTO chat_messages_fts(chat_messages_fts) VALUES ('rebuild');
                """)
                self.fts_enabled = True
            except sqlite3.OperationalError:
                self.fts_enabled = False

    def create_session(self, title: str = "新对话", model: str = "") -> int:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO chat_sessions (title, created_at, updated_at, model) VALUES (?, ?, ?, ?)",
                (title, now, now, model),
            )
            return int(cursor.lastrowid)

    def list_sessions(self, limit: int = 80) -> list[ChatSession]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT s.id, s.title, s.created_at, s.updated_at, COUNT(m.id) AS message_count
                FROM chat_sessions s
                LEFT JOIN chat_messages m ON m.session_id = s.id
                GROUP BY s.id
                ORDER BY s.updated_at DESC, s.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            ChatSession(
                id=int(row["id"]),
                title=str(row["title"]),
                created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
                message_count=int(row["message_count"] or 0),
            )
            for row in rows
        ]

    def messages(self, session_id: int) -> list[dict[str, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
        return [{"role": str(row["role"]), "content": str(row["content"])} for row in rows]

    def add_message(self, session_id: int, role: str, content: str) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO chat_messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (session_id, role, content, now),
            )
            conn.execute("UPDATE chat_sessions SET updated_at = ? WHERE id = ?", (now, session_id))

    def rename_session(self, session_id: int, title: str) -> None:
        title = title.strip()[:80] or "新对话"
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute("UPDATE chat_sessions SET title = ?, updated_at = ? WHERE id = ?", (title, now, session_id))

    def search(self, query: str, limit: int = 50) -> list[ChatSearchResult]:
        query = query.strip()
        if not query:
            return []
        with self._connect() as conn:
            if self.fts_enabled:
                rows = conn.execute(
                    "SELECT f.session_id, s.title, f.role, snippet(chat_messages_fts, 0, '[', ']', '…', 24) AS snippet, m.created_at FROM chat_messages_fts f JOIN chat_messages m ON m.id=f.rowid JOIN chat_sessions s ON s.id=f.session_id WHERE chat_messages_fts MATCH ? ORDER BY bm25(chat_messages_fts) LIMIT ?",
                    (query, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT m.session_id, s.title, m.role, substr(m.content, 1, 300) AS snippet, m.created_at FROM chat_messages m JOIN chat_sessions s ON s.id=m.session_id WHERE m.content LIKE ? ORDER BY m.id DESC LIMIT ?",
                    (f"%{query}%", limit),
                ).fetchall()
        return [ChatSearchResult(int(row["session_id"]), str(row["title"]), str(row["role"]), str(row["snippet"]), str(row["created_at"])) for row in rows]

    def delete_session(self, session_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
