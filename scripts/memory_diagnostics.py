"""Privacy-safe diagnostics for AURA v0.6 memory & continuity."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from config.settings import settings  # noqa: E402
from database.database import Database  # noqa: E402
from memory.manager import MemoryManager  # noqa: E402


def main() -> int:
    print("=== AURA v0.6 - MEMORY & CONTINUITY DIAGNOSTICS ===", flush=True)
    print(f"Application       : {settings.APP_NAME} v{settings.APP_VERSION}", flush=True)
    print(f"Database          : {settings.DB_PATH}", flush=True)
    print(f"Memory enabled    : {settings.MEMORY_ENABLED}", flush=True)
    print(f"Auto capture      : {settings.MEMORY_AUTO_CAPTURE}", flush=True)
    print(f"Context limit     : {settings.MEMORY_CONTEXT_LIMIT}", flush=True)
    print(f"Sensitive context : {settings.MEMORY_ALLOW_SENSITIVE_CONTEXT}", flush=True)

    db = Database(settings.DB_PATH)
    try:
        memory = MemoryManager(db)
        active = int(db.conn.execute("SELECT COUNT(*) FROM memories WHERE status='ACTIVE'").fetchone()[0])
        sensitive = int(db.conn.execute("SELECT COUNT(*) FROM memories WHERE status='ACTIVE' AND is_sensitive=1").fetchone()[0])
        sessions = int(db.conn.execute("SELECT COUNT(*) FROM conversation_sessions").fetchone()[0])
        tasks = int(db.conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0])
        reminders = int(db.conn.execute("SELECT COUNT(*) FROM reminders").fetchone()[0])

        print(f"Active memories   : {active}", flush=True)
        print(f"Sensitive records : {sensitive}", flush=True)
        print(f"Session metadata  : {sessions}", flush=True)
        print(f"Tasks preserved   : {tasks}", flush=True)
        print(f"Reminders kept    : {reminders}", flush=True)

        cols = {row["name"] for row in db.conn.execute("PRAGMA table_info(memories)").fetchall()}
        required = {
            "updated_at", "normalized_content", "status", "access_count",
            "last_used_context_at", "is_sensitive", "tags",
        }
        missing = sorted(required - cols)
        if missing:
            print(f"[FAIL] Colonnes mémoire manquantes: {', '.join(missing)}", flush=True)
            return 2

        pref_table = db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='preferences'"
        ).fetchone()
        if not pref_table:
            print("[FAIL] Table preferences absente.", flush=True)
            return 3
        print("Relationship model: schema OK", flush=True)
        print("[PASS] Mémoire locale et continuité opérationnelles.", flush=True)
        print("       Aucun contenu privé n'a été affiché par ce diagnostic.", flush=True)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
