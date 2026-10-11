"""Versioned SQLite schema for the native AURA profile."""
from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

SCHEMA_VERSION = 13

MIGRATION_1 = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memories (
    memory_id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    normalized_content TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    scope TEXT NOT NULL,
    scope_id TEXT NOT NULL,
    importance INTEGER NOT NULL DEFAULT 3 CHECK (importance BETWEEN 1 AND 5),
    confidence REAL NOT NULL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    source TEXT NOT NULL,
    is_sensitive INTEGER NOT NULL DEFAULT 0 CHECK (is_sensitive IN (0,1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_memories_active_normalized
ON memories(scope, scope_id, normalized_content)
WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_memories_active_updated
ON memories(status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_memories_scope
ON memories(scope, scope_id, status);

CREATE TABLE IF NOT EXISTS memory_audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id TEXT NOT NULL,
    action TEXT NOT NULL,
    at TEXT NOT NULL,
    detail_json TEXT NOT NULL DEFAULT '{}'
);
"""

MIGRATION_10 = """
ALTER TABLE local_reminders ADD COLUMN claimed_at TEXT NULL;
ALTER TABLE local_reminders ADD COLUMN notified_at TEXT NULL;
ALTER TABLE local_reminders ADD COLUMN expired_at TEXT NULL;
"""
MIGRATION_11 = """
CREATE TABLE IF NOT EXISTS local_notes (
    note_id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_local_notes_updated ON local_notes(updated_at, note_id);
"""
MIGRATION_12 = """
CREATE TABLE IF NOT EXISTS developer_jobs (job_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS developer_audit (
 event_id TEXT PRIMARY KEY, job_id TEXT, timestamp REAL NOT NULL,
 event_type TEXT NOT NULL, metadata TEXT NOT NULL,
 prev_hash TEXT NOT NULL, hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_developer_audit_time ON developer_audit(timestamp, event_id);
"""
MIGRATION_13 = """
ALTER TABLE developer_audit ADD COLUMN sequence INTEGER;
UPDATE developer_audit SET sequence = rowid WHERE sequence IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_developer_audit_sequence ON developer_audit(sequence);
"""

MIGRATION_2 = """
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'qml'
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_created
ON messages(conversation_id, created_at, message_id);
CREATE INDEX IF NOT EXISTS idx_conversations_updated
ON conversations(status, updated_at DESC, conversation_id);
"""

MIGRATION_3 = """
CREATE TABLE IF NOT EXISTS conversation_messages (
    message_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    source TEXT NOT NULL DEFAULT 'qml',
    UNIQUE(conversation_id, sequence)
);
CREATE INDEX IF NOT EXISTS idx_conversation_messages_order
ON conversation_messages(conversation_id, sequence, message_id);
CREATE INDEX IF NOT EXISTS idx_conversations_session_updated
ON conversations(session_id, status, updated_at DESC, conversation_id);
"""

MIGRATION_4 = """
CREATE TABLE IF NOT EXISTS agent_requests (
    request_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    user_message_id TEXT NOT NULL,
    prompt TEXT NOT NULL,
    state TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    source TEXT NOT NULL,
    error_code TEXT NOT NULL DEFAULT '',
    error_message TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_agent_requests_session_updated
ON agent_requests(session_id, updated_at DESC, request_id);
"""
MIGRATION_5 = """
CREATE TABLE IF NOT EXISTS prepared_actions (action_id TEXT PRIMARY KEY,tool_name TEXT NOT NULL,action_type TEXT NOT NULL,payload_json TEXT NOT NULL,summary TEXT NOT NULL,requires_confirmation INTEGER NOT NULL,state TEXT NOT NULL,created_at TEXT NOT NULL,expires_at TEXT,confirmed_at TEXT,executed_at TEXT,error_code TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS idx_prepared_actions_state ON prepared_actions(state);
CREATE INDEX IF NOT EXISTS idx_prepared_actions_expiry ON prepared_actions(expires_at);
"""
MIGRATION_6 = """
CREATE TABLE IF NOT EXISTS provider_settings (provider_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL, selected_model TEXT NOT NULL, base_url TEXT NOT NULL, is_active INTEGER NOT NULL, configured INTEGER NOT NULL, updated_at TEXT NOT NULL);
"""
MIGRATION_7 = """
CREATE TABLE IF NOT EXISTS local_tasks (
    task_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    due TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_local_tasks_created ON local_tasks(created_at, task_id);
"""
MIGRATION_8 = """
ALTER TABLE local_tasks ADD COLUMN completed INTEGER NOT NULL DEFAULT 0;
ALTER TABLE local_tasks ADD COLUMN updated_at TEXT NOT NULL DEFAULT '';
"""
MIGRATION_9 = """
CREATE TABLE IF NOT EXISTS local_reminders (
    reminder_id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    trigger_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_local_reminders_trigger ON local_reminders(trigger_at, reminder_id);
"""

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")

def migrate(conn: sqlite3.Connection) -> int:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    row = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()
    current = int(row[0] if row else 0)
    if current > SCHEMA_VERSION:
        raise RuntimeError(f"database schema {current} is newer than supported {SCHEMA_VERSION}")
    if current < 1:
        conn.executescript(MIGRATION_1)
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(?, ?)",
            (1, _utc_now()),
        )
        current = 1
    if current < 2:
        conn.executescript(MIGRATION_2)
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(?, ?)",
            (2, _utc_now()),
        )
        current = 2
    if current < 3:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(conversations)").fetchall()}
        if "session_id" not in columns:
            conn.execute("ALTER TABLE conversations ADD COLUMN session_id TEXT NOT NULL DEFAULT 'legacy-v2'")
        conn.executescript(MIGRATION_3)
        # v2 remains untouched. Copy each legacy message once with an explicit,
        # deterministic per-conversation sequence.
        legacy_exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='messages'").fetchone()
        if legacy_exists:
            rows = conn.execute("SELECT message_id,conversation_id,role,content,created_at,source FROM messages ORDER BY conversation_id,created_at,message_id").fetchall()
            sequence_by_conversation: dict[str, int] = {}
            for row in rows:
                conversation_id = str(row[1]); sequence_by_conversation[conversation_id] = sequence_by_conversation.get(conversation_id, 0) + 1
                conn.execute(
                    "INSERT OR IGNORE INTO conversation_messages(message_id,conversation_id,role,content,created_at,sequence,status,source) VALUES(?,?,?,?,?,?,?,?)",
                    (row[0], conversation_id, row[2], row[3], row[4], sequence_by_conversation[conversation_id], "active", row[5]),
                )
        conn.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(?, ?)", (3, _utc_now()))
        current = 3
    if current < 4:
        conn.executescript(MIGRATION_4)
        conn.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(?, ?)", (4, _utc_now()))
        current = 4
    if current < 5:
        conn.executescript(MIGRATION_5)
        conn.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(?, ?)", (5, _utc_now()))
        current = 5
    if current < 6:
        conn.executescript(MIGRATION_6)
        conn.execute("INSERT INTO schema_migrations(version, applied_at) VALUES(?, ?)", (6, _utc_now()))
        current = 6
    if current < 7:
        conn.executescript(MIGRATION_7)
        conn.execute("INSERT INTO schema_migrations(version, applied_at) VALUES(?, ?)", (7, _utc_now()))
        current = 7
    if current < 8:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(local_tasks)").fetchall()}
        if "completed" not in columns:
            conn.execute("ALTER TABLE local_tasks ADD COLUMN completed INTEGER NOT NULL DEFAULT 0")
        if "updated_at" not in columns:
            conn.execute("ALTER TABLE local_tasks ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")
        conn.execute("UPDATE local_tasks SET updated_at=created_at WHERE updated_at='' ")
        conn.execute("INSERT INTO schema_migrations(version, applied_at) VALUES(?, ?)", (8, _utc_now()))
        current = 8
    if current < 9:
        conn.executescript(MIGRATION_9)
        conn.execute("INSERT INTO schema_migrations(version, applied_at) VALUES(?, ?)", (9, _utc_now()))
        current = 9
    if current < 10:
        conn.executescript(MIGRATION_10)
        conn.execute("INSERT INTO schema_migrations(version, applied_at) VALUES(?, ?)", (10, _utc_now()))
        current = 10
    if current < 11:
        conn.executescript(MIGRATION_11)
        conn.execute("INSERT INTO schema_migrations(version, applied_at) VALUES(?, ?)", (11, _utc_now()))
        current = 11
    if current < 12:
        conn.executescript(MIGRATION_12)
        conn.execute("INSERT INTO schema_migrations(version, applied_at) VALUES(?, ?)", (12, _utc_now()))
        current = 12
    if current < 13:
        columns={r[1] for r in conn.execute('PRAGMA table_info(developer_audit)').fetchall()}
        if 'sequence' not in columns:
            conn.executescript(MIGRATION_13)
        conn.execute("INSERT INTO schema_migrations(version, applied_at) VALUES(?, ?)", (13, _utc_now()))
        current = 13
    return SCHEMA_VERSION
