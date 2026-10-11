"""SQLite repository for native memories."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
import unicodedata
from uuid import uuid4

from aura_native.memory.models import MemoryRecord
from aura_native.storage.database import NativeDatabase

_ALLOWED_TYPES = {"fact", "preference", "project", "goal", "habit", "note"}
_ALLOWED_SCOPES = {"user", "session", "project"}

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")

def normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", str(text or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"\s+", " ", value.casefold()).strip()
    return value

def _tokens(text: str) -> set[str]:
    return {x for x in re.findall(r"[a-z0-9_]+", normalize(text)) if len(x) > 1}

class MemoryRepository:
    def __init__(self, database: NativeDatabase) -> None:
        self.db = database

    @staticmethod
    def _record(row) -> MemoryRecord:
        return MemoryRecord(
            memory_id=row["memory_id"],
            content=row["content"],
            normalized_content=row["normalized_content"],
            memory_type=row["memory_type"],
            scope=row["scope"],
            scope_id=row["scope_id"],
            importance=int(row["importance"]),
            confidence=float(row["confidence"]),
            source=row["source"],
            is_sensitive=bool(row["is_sensitive"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
            status=row["status"],
        )

    def create(
        self,
        content: str,
        *,
        memory_type: str = "fact",
        scope: str = "user",
        scope_id: str = "default",
        importance: int = 3,
        confidence: float = 1.0,
        source: str = "explicit_user",
        is_sensitive: bool = False,
    ) -> tuple[MemoryRecord, bool]:
        content = str(content or "").strip()
        if not content:
            raise ValueError("memory content must not be empty")
        memory_type = str(memory_type or "fact").strip().lower()
        scope = str(scope or "user").strip().lower()
        scope_id = str(scope_id or "").strip()
        if memory_type not in _ALLOWED_TYPES:
            raise ValueError("unsupported memory_type")
        if scope not in _ALLOWED_SCOPES:
            raise ValueError("unsupported memory scope")
        if not scope_id:
            raise ValueError("scope_id is required")
        importance = max(1, min(5, int(importance)))
        confidence = max(0.0, min(1.0, float(confidence)))
        source = str(source or "explicit_user").strip()[:80] or "explicit_user"
        normalized = normalize(content)
        now = _utc_now()

        with self.db.transaction() as conn:
            existing = conn.execute(
                "SELECT * FROM memories WHERE scope=? AND scope_id=? AND normalized_content=? AND status='active' LIMIT 1",
                (scope, scope_id, normalized),
            ).fetchone()
            if existing is not None:
                new_importance = max(int(existing["importance"]), importance)
                new_confidence = max(float(existing["confidence"]), confidence)
                conn.execute(
                    "UPDATE memories SET importance=?,confidence=?,updated_at=?,source=?,is_sensitive=? WHERE memory_id=?",
                    (new_importance, new_confidence, now, source, int(bool(is_sensitive or existing["is_sensitive"])), existing["memory_id"]),
                )
                row = conn.execute("SELECT * FROM memories WHERE memory_id=?", (existing["memory_id"],)).fetchone()
                return self._record(row), False

            memory_id = str(uuid4())
            conn.execute(
                "INSERT INTO memories(memory_id,content,normalized_content,memory_type,scope,scope_id,importance,confidence,source,is_sensitive,created_at,updated_at,expires_at,status) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'active')",
                (memory_id, content, normalized, memory_type, scope, scope_id, importance, confidence, source, int(bool(is_sensitive)), now, now, None),
            )
            conn.execute(
                "INSERT INTO memory_audit(memory_id,action,at,detail_json) VALUES(?,?,?,?)",
                (memory_id, "create", now, json.dumps({"scope": scope, "scope_id": scope_id, "memory_type": memory_type}, sort_keys=True)),
            )
            row = conn.execute("SELECT * FROM memories WHERE memory_id=?", (memory_id,)).fetchone()
            return self._record(row), True

    def get(self, memory_id: str, *, include_sensitive: bool = False) -> MemoryRecord | None:
        with self.db.reader() as conn:
            row = conn.execute(
                "SELECT * FROM memories WHERE memory_id=? AND status='active'",
                (str(memory_id),),
            ).fetchone()
        if row is None:
            return None
        record = self._record(row)
        if record.is_sensitive and not include_sensitive:
            return None
        return record

    def list(self, *, limit: int = 20, scope: str | None = None, scope_id: str | None = None, include_sensitive: bool = False) -> list[MemoryRecord]:
        limit = max(1, min(int(limit), 100))
        sql = "SELECT * FROM memories WHERE status='active'"
        params: list[object] = []
        if not include_sensitive:
            sql += " AND is_sensitive=0"
        if scope is not None:
            sql += " AND scope=?"
            params.append(str(scope))
        if scope_id is not None:
            sql += " AND scope_id=?"
            params.append(str(scope_id))
        sql += " ORDER BY importance DESC, updated_at DESC, memory_id ASC LIMIT ?"
        params.append(limit)
        with self.db.reader() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._record(row) for row in rows]

    def search(self, query: str, *, limit: int = 10, include_sensitive: bool = False) -> list[MemoryRecord]:
        query = str(query or "").strip()
        candidates = self.list(limit=100, include_sensitive=include_sensitive)
        if not query:
            return candidates[: max(1, min(int(limit), 100))]
        q = _tokens(query)
        ranked = []
        for record in candidates:
            tokens = _tokens(record.content)
            overlap = len(q & tokens)
            if overlap:
                coverage = overlap / max(1, len(q))
                specificity = overlap / max(1, len(tokens))
                score = coverage * 0.75 + specificity * 0.25 + record.importance * 0.04 + record.confidence * 0.10
                ranked.append((score, record.updated_at, record.memory_id, record))
        ranked.sort(reverse=True)
        return [item[3] for item in ranked[: max(1, min(int(limit), 100))]]

    def forget(self, memory_id: str) -> MemoryRecord | None:
        memory_id = str(memory_id or "").strip()
        if not memory_id:
            return None
        with self.db.transaction() as conn:
            row = conn.execute("SELECT * FROM memories WHERE memory_id=? AND status='active'", (memory_id,)).fetchone()
            if row is None:
                return None
            record = self._record(row)
            now = _utc_now()
            conn.execute(
                "INSERT INTO memory_audit(memory_id,action,at,detail_json) VALUES(?,?,?,?)",
                (memory_id, "forget", now, json.dumps({"memory_type": record.memory_type, "scope": record.scope, "scope_id": record.scope_id}, sort_keys=True)),
            )
            conn.execute("DELETE FROM memories WHERE memory_id=?", (memory_id,))
            return record

    def clear_session(self, session_id: str) -> int:
        session_id = str(session_id or "").strip()
        if not session_id:
            return 0
        with self.db.transaction() as conn:
            rows = conn.execute(
                "SELECT memory_id FROM memories WHERE scope='session' AND scope_id=?",
                (session_id,),
            ).fetchall()
            now = _utc_now()
            for row in rows:
                conn.execute(
                    "INSERT INTO memory_audit(memory_id,action,at,detail_json) VALUES(?,?,?,?)",
                    (row["memory_id"], "clear_session", now, json.dumps({"scope_id": session_id}, sort_keys=True)),
                )
            conn.execute("DELETE FROM memories WHERE scope='session' AND scope_id=?", (session_id,))
            return len(rows)
