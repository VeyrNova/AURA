"""SQLite storage layer for AURA.

v0.6 keeps all existing data and applies non-destructive schema migrations for
persistent memory and session continuity.
"""
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from config.settings import settings

logger = logging.getLogger("aura.database")

SCHEMA = """
CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS security_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    action TEXT NOT NULL,
    risk TEXT NOT NULL,
    allowed INTEGER NOT NULL,
    reason TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    content TEXT NOT NULL,
    tags TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    priority TEXT,
    status TEXT DEFAULT 'TODO',
    category TEXT,
    tags TEXT,
    due_date TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    trigger_at TEXT NOT NULL,
    is_done INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    date TEXT NOT NULL,
    time TEXT,
    duration TEXT,
    location TEXT,
    description TEXT,
    reminder_minutes_before INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    type TEXT NOT NULL,
    importance INTEGER DEFAULT 1,
    source TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT NOT NULL,
    last_accessed_at TEXT
);

CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversation_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    user_messages INTEGER DEFAULT 0,
    assistant_messages INTEGER DEFAULT 0,
    private_mode INTEGER DEFAULT 0
);
"""


class Database:
    """Access to AURA's local SQLite database.

    `db_path` is optional and exists mainly to make security/unit tests isolated.
    """

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path is not None else settings.DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._migrate_v060_memory_schema()
        self.conn.commit()
        logger.info("Base de donnees initialisee : %s", self.db_path)

    def _migrate_v060_memory_schema(self) -> None:
        """Add v0.6 memory columns without destroying an existing database."""
        columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(memories)").fetchall()}
        additions = {
            "updated_at": "TEXT",
            "normalized_content": "TEXT",
            "status": "TEXT DEFAULT 'ACTIVE'",
            "access_count": "INTEGER DEFAULT 0",
            "last_used_context_at": "TEXT",
            "is_sensitive": "INTEGER DEFAULT 0",
            "tags": "TEXT",
        }
        for name, definition in additions.items():
            if name not in columns:
                self.conn.execute(f"ALTER TABLE memories ADD COLUMN {name} {definition}")

        now = datetime.now().astimezone().isoformat(timespec="seconds")
        self.conn.execute("UPDATE memories SET status='ACTIVE' WHERE status IS NULL OR status='' ")
        self.conn.execute("UPDATE memories SET access_count=0 WHERE access_count IS NULL")
        self.conn.execute("UPDATE memories SET is_sensitive=0 WHERE is_sensitive IS NULL")
        self.conn.execute("UPDATE memories SET updated_at=COALESCE(updated_at, created_at, ?) WHERE updated_at IS NULL", (now,))

        # Backfill a conservative normalized value for legacy memories. The full
        # accent-insensitive normalization is applied by MemoryManager for new data.
        rows = self.conn.execute(
            "SELECT id, content FROM memories WHERE normalized_content IS NULL OR normalized_content=''"
        ).fetchall()
        for row in rows:
            normalized = " ".join(str(row["content"] or "").lower().split())
            self.conn.execute("UPDATE memories SET normalized_content=? WHERE id=?", (normalized, row["id"]))

        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_status_importance ON memories(status, importance DESC)"
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_normalized ON memories(normalized_content)"
        )

    def get_preference(self, key: str):
        row = self.conn.execute("SELECT value FROM preferences WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def set_preference(self, key: str, value: str) -> None:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        self.conn.execute(
            "INSERT INTO preferences(key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, str(value), now),
        )
        self.conn.commit()

    def log_activity(self, message: str):
        self.conn.execute(
            "INSERT INTO activity_log (timestamp, message) VALUES (?, ?)",
            (datetime.now().isoformat(timespec="seconds"), message),
        )
        self.conn.commit()

    def log_security_audit(self, action: str, risk: str, allowed: bool, reason: str):
        self.conn.execute(
            "INSERT INTO security_audit (timestamp, action, risk, allowed, reason) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                datetime.now().isoformat(timespec="seconds"),
                action,
                risk,
                1 if allowed else 0,
                reason,
            ),
        )
        self.conn.commit()

    def close(self):
        self.conn.close()
