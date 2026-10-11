"""Small SQLite boundary with no historical path discovery."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3

from aura_native.storage.migrations import migrate

class NativeDatabase:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _prepare_parent(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        self._prepare_parent()
        conn = sqlite3.connect(str(self.path), timeout=10.0)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=10000")
            migrate(conn)
            # Commit schema setup before repository code starts BEGIN IMMEDIATE.
            conn.commit()
            return conn
        except Exception:
            conn.close()
            raise

    @contextmanager
    def transaction(self):
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def reader(self):
        conn = self.connect()
        try:
            yield conn
        finally:
            conn.close()
