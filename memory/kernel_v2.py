# AURA v0.8.7 - MemoryKernel v2 canonical implementation
from __future__ import annotations

import json
import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable


class MemoryType(str, Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PREFERENCE = "preference"
    PROJECT = "project"


class MemoryScope(str, Enum):
    SESSION = "session"
    USER = "user"
    PROJECT = "project"


@dataclass(frozen=True)
class MemoryRecordV2:
    memory_id: str
    memory_type: MemoryType
    scope: MemoryScope
    scope_id: str
    content: str
    provenance: dict[str, Any]
    version: int
    created_at: str
    updated_at: str
    expires_at: str | None = None
    status: str = "active"
    merged_into_id: str | None = None
    is_sensitive: bool = False


class MemoryKernelV2:
    MEMORY_KERNEL_VERSION = "2"
    RECORDS_TABLE = "memory_kernel_v2_records"
    AUDIT_TABLE = "memory_kernel_v2_audit"

    _SCHEMA_SQL = (
        "BEGIN IMMEDIATE;"
        "CREATE TABLE IF NOT EXISTS memory_kernel_v2_records ("
        "memory_id TEXT PRIMARY KEY,"
        "memory_type TEXT NOT NULL,"
        "scope TEXT NOT NULL,"
        "scope_id TEXT NOT NULL DEFAULT '',"
        "content TEXT NOT NULL,"
        "provenance_json TEXT NOT NULL DEFAULT '{}',"
        "version INTEGER NOT NULL DEFAULT 1,"
        "created_at TEXT NOT NULL,"
        "updated_at TEXT NOT NULL,"
        "expires_at TEXT,"
        "status TEXT NOT NULL DEFAULT 'active',"
        "merged_into_id TEXT,"
        "is_sensitive INTEGER NOT NULL DEFAULT 0,"
        "CHECK (memory_type IN ('episodic','semantic','preference','project')),"
        "CHECK (scope IN ('session','user','project')),"
        "CHECK (version >= 1)"
        ");"
        "CREATE INDEX IF NOT EXISTS idx_memory_kernel_v2_scope "
        "ON memory_kernel_v2_records(scope,scope_id,memory_type,status);"
        "CREATE INDEX IF NOT EXISTS idx_memory_kernel_v2_updated "
        "ON memory_kernel_v2_records(updated_at DESC,memory_id ASC);"
        "CREATE INDEX IF NOT EXISTS idx_memory_kernel_v2_expiry "
        "ON memory_kernel_v2_records(expires_at,status);"
        "CREATE TABLE IF NOT EXISTS memory_kernel_v2_audit ("
        "audit_id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "memory_id TEXT NOT NULL,"
        "action TEXT NOT NULL,"
        "at TEXT NOT NULL,"
        "version INTEGER,"
        "detail_json TEXT NOT NULL DEFAULT '{}'"
        ");"
        "CREATE INDEX IF NOT EXISTS idx_memory_kernel_v2_audit_memory "
        "ON memory_kernel_v2_audit(memory_id,audit_id);"
        "COMMIT;"
    )

    def __init__(self, db_path: str | Path | None = None, *, policy_guard: Callable[[str, dict[str, Any]], bool] | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else self._default_db_path()
        self.policy_guard = policy_guard
        self._working: dict[str, MemoryRecordV2] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _default_db_path() -> Path:
        return Path(__file__).resolve().parents[1] / "database" / "aura.db"

    @classmethod
    def from_legacy_manager(cls, manager: Any) -> "MemoryKernelV2":
        for attr in ("db_path", "database_path", "_db_path"):
            value = getattr(manager, attr, None)
            if value:
                return cls(value)
        for owner_name in ("db", "database", "_db"):
            owner = getattr(manager, owner_name, None)
            if owner is None:
                continue
            for attr in ("db_path", "database_path", "path", "_path"):
                value = getattr(owner, attr, None)
                if value:
                    return cls(value)
        return cls()

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="microseconds")

    @staticmethod
    def _parse_time(value: str | None) -> datetime | None:
        if not value:
            return None
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _memory_type(value: MemoryType | str) -> MemoryType:
        return value if isinstance(value, MemoryType) else MemoryType(str(value).strip().lower())

    @staticmethod
    def _scope(value: MemoryScope | str) -> MemoryScope:
        return value if isinstance(value, MemoryScope) else MemoryScope(str(value).strip().lower())

    @staticmethod
    def _scope_id(scope: MemoryScope, value: str | None) -> str:
        text = str(value or "").strip()
        if text:
            return text
        if scope is MemoryScope.USER:
            return "default"
        raise ValueError("scope_id is required for session/project scope")

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {x for x in re.findall(r"[a-z0-9_]+", str(text).lower()) if len(x) > 1}

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        try:
            conn.executescript(self._SCHEMA_SQL)
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            conn.close()

    def _guard(self, action: str, payload: dict[str, Any]) -> None:
        if self.policy_guard is None:
            return
        try:
            allowed = bool(self.policy_guard(action, dict(payload)))
        except Exception as exc:
            raise PermissionError("MemoryKernel v2 policy guard failed closed") from exc
        if not allowed:
            raise PermissionError("MemoryKernel v2 policy guard denied " + action)

    def _audit(self, conn: sqlite3.Connection, memory_id: str, action: str, version: int | None, detail: dict[str, Any] | None = None) -> None:
        conn.execute(
            "INSERT INTO memory_kernel_v2_audit(memory_id,action,at,version,detail_json) VALUES(?,?,?,?,?)",
            (memory_id, action, self._utc_now(), version, json.dumps(detail or {}, sort_keys=True, ensure_ascii=False)),
        )

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> MemoryRecordV2:
        try:
            provenance = json.loads(row["provenance_json"] or "{}")
        except Exception:
            provenance = {"decode_error": True}
        if not isinstance(provenance, dict):
            provenance = {"value": provenance}
        return MemoryRecordV2(
            memory_id=row["memory_id"],
            memory_type=MemoryType(row["memory_type"]),
            scope=MemoryScope(row["scope"]),
            scope_id=row["scope_id"],
            content=row["content"],
            provenance=provenance,
            version=int(row["version"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
            status=row["status"],
            merged_into_id=row["merged_into_id"],
            is_sensitive=bool(row["is_sensitive"]),
        )

    def remember(self, content: str, *, memory_type: MemoryType | str, scope: MemoryScope | str, scope_id: str | None = None, provenance: dict[str, Any] | None = None, expires_at: str | None = None, is_sensitive: bool = False, memory_id: str | None = None) -> MemoryRecordV2:
        mt = self._memory_type(memory_type)
        sc = self._scope(scope)
        sid = self._scope_id(sc, scope_id)
        text = str(content).strip()
        if not text:
            raise ValueError("memory content must not be empty")
        expiry = self._parse_time(expires_at)
        expiry_text = expiry.isoformat(timespec="microseconds") if expiry else None
        mid = str(memory_id or uuid.uuid4())
        now = self._utc_now()
        prov = dict(provenance or {})
        prov.setdefault("kernel", "MemoryKernelV2")
        prov.setdefault("created_by", "explicit")
        self._guard("memory.remember", {"memory_id": mid, "memory_type": mt.value, "scope": sc.value, "scope_id": sid})

        record = MemoryRecordV2(mid, mt, sc, sid, text, prov, 1, now, now, expiry_text, "active", None, bool(is_sensitive))
        if mt is MemoryType.WORKING:
            with self._lock:
                if mid in self._working:
                    raise ValueError("duplicate memory_id")
                self._working[mid] = record
            return record

        self.ensure_schema()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO memory_kernel_v2_records(memory_id,memory_type,scope,scope_id,content,provenance_json,version,created_at,updated_at,expires_at,status,merged_into_id,is_sensitive) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (mid, mt.value, sc.value, sid, text, json.dumps(prov, sort_keys=True, ensure_ascii=False), 1, now, now, expiry_text, "active", None, int(bool(is_sensitive))),
            )
            self._audit(conn, mid, "remember", 1, {"memory_type": mt.value, "scope": sc.value, "scope_id": sid})
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return record

    def get(self, memory_id: str, *, include_inactive: bool = False, include_sensitive: bool = False) -> MemoryRecordV2 | None:
        mid = str(memory_id)
        with self._lock:
            working = self._working.get(mid)
        if working is not None:
            if working.status != "active" and not include_inactive:
                return None
            if working.is_sensitive and not include_sensitive:
                return None
            return working

        self.ensure_schema()
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM memory_kernel_v2_records WHERE memory_id=?", (mid,)).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        record = self._row_to_record(row)
        if record.status != "active" and not include_inactive:
            return None
        if record.is_sensitive and not include_sensitive:
            return None
        if record.expires_at and self._parse_time(record.expires_at) <= datetime.now(timezone.utc) and not include_inactive:
            return None
        return record

    def retrieve(self, query: str = "", *, memory_types: Iterable[MemoryType | str] | None = None, scope: MemoryScope | str | None = None, scope_id: str | None = None, limit: int = 10, include_inactive: bool = False, include_sensitive: bool = False) -> list[MemoryRecordV2]:
        limit = max(1, min(int(limit), 100))
        types = {self._memory_type(x) for x in memory_types} if memory_types is not None else None
        sc = self._scope(scope) if scope is not None else None
        sid = str(scope_id).strip() if scope_id is not None else None
        q_tokens = self._tokens(query)
        candidates: list[MemoryRecordV2] = []

        with self._lock:
            for record in self._working.values():
                if types is not None and record.memory_type not in types:
                    continue
                if sc is not None and record.scope is not sc:
                    continue
                if sid is not None and record.scope_id != sid:
                    continue
                if record.status != "active" and not include_inactive:
                    continue
                if record.is_sensitive and not include_sensitive:
                    continue
                if record.expires_at and self._parse_time(record.expires_at) <= datetime.now(timezone.utc) and not include_inactive:
                    continue
                candidates.append(record)

        self.ensure_schema()
        sql = "SELECT * FROM memory_kernel_v2_records WHERE 1=1"
        params: list[Any] = []
        if types is not None:
            durable = sorted(x.value for x in types if x is not MemoryType.WORKING)
            if durable:
                sql += " AND memory_type IN (" + ",".join("?" for _ in durable) + ")"
                params.extend(durable)
            else:
                sql += " AND 0"
        if sc is not None:
            sql += " AND scope=?"
            params.append(sc.value)
        if sid is not None:
            sql += " AND scope_id=?"
            params.append(sid)
        if not include_inactive:
            sql += " AND status='active'"
        if not include_sensitive:
            sql += " AND is_sensitive=0"
        sql += " ORDER BY updated_at DESC,memory_id ASC LIMIT 500"

        conn = self._connect()
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()

        now = datetime.now(timezone.utc)
        for row in rows:
            record = self._row_to_record(row)
            if record.expires_at and self._parse_time(record.expires_at) <= now and not include_inactive:
                continue
            candidates.append(record)

        def key(record: MemoryRecordV2) -> tuple[int, str, str]:
            overlap = len(q_tokens & self._tokens(record.content)) if q_tokens else 0
            return (overlap, record.updated_at, record.memory_id)

        candidates.sort(key=key, reverse=True)
        return candidates[:limit]

    def update(self, memory_id: str, *, content: str | None = None, provenance: dict[str, Any] | None = None, expires_at: str | None = None, clear_expiry: bool = False) -> MemoryRecordV2:
        existing = self.get(memory_id, include_inactive=True, include_sensitive=True)
        if existing is None:
            raise KeyError(memory_id)
        self._guard("memory.update", {"memory_id": memory_id, "version": existing.version})
        new_content = existing.content if content is None else str(content).strip()
        if not new_content:
            raise ValueError("memory content must not be empty")
        new_prov = dict(existing.provenance)
        if provenance:
            new_prov.update(provenance)
        lineage = new_prov.get("lineage")
        if not isinstance(lineage, dict):
            lineage = {}
        lineage["previous_version"] = existing.version
        new_prov["lineage"] = lineage
        if clear_expiry:
            expiry_text = None
        elif expires_at is not None:
            expiry = self._parse_time(expires_at)
            expiry_text = expiry.isoformat(timespec="microseconds") if expiry else None
        else:
            expiry_text = existing.expires_at
        now = self._utc_now()
        updated = replace(existing, content=new_content, provenance=new_prov, version=existing.version + 1, updated_at=now, expires_at=expiry_text, status="active")

        if existing.memory_type is MemoryType.WORKING:
            with self._lock:
                self._working[memory_id] = updated
            return updated

        self.ensure_schema()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE memory_kernel_v2_records SET content=?,provenance_json=?,version=?,updated_at=?,expires_at=?,status='active' WHERE memory_id=?",
                (updated.content, json.dumps(updated.provenance, sort_keys=True, ensure_ascii=False), updated.version, updated.updated_at, updated.expires_at, memory_id),
            )
            self._audit(conn, memory_id, "update", updated.version, {"previous_version": existing.version})
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return updated

    def merge(self, source_ids: Iterable[str], *, target_id: str | None = None, provenance: dict[str, Any] | None = None) -> MemoryRecordV2:
        ids = [str(x) for x in source_ids]
        if len(ids) < 2:
            raise ValueError("merge requires at least two memories")
        sources = [self.get(mid, include_inactive=True, include_sensitive=True) for mid in ids]
        if any(x is None for x in sources):
            raise KeyError("one or more merge sources are missing")
        records = [x for x in sources if x is not None]
        first = records[0]
        if any(x.memory_type is MemoryType.WORKING for x in records):
            raise ValueError("working memory cannot be durably merged")
        if any(x.memory_type is not first.memory_type for x in records):
            raise ValueError("merge requires same memory_type")
        if any((x.scope, x.scope_id) != (first.scope, first.scope_id) for x in records):
            raise ValueError("merge requires same scope")
        self._guard("memory.merge", {"source_ids": ids, "target_id": target_id})

        mid = str(target_id or uuid.uuid4())
        now = self._utc_now()
        merged_prov = dict(provenance or {})
        merged_prov["kernel"] = "MemoryKernelV2"
        merged_prov["merged_from"] = [{"memory_id": x.memory_id, "version": x.version, "provenance": x.provenance} for x in records]
        merged_content = "\n".join(dict.fromkeys(x.content for x in records))
        merged = MemoryRecordV2(mid, first.memory_type, first.scope, first.scope_id, merged_content, merged_prov, 1, now, now, None, "active", None, any(x.is_sensitive for x in records))

        self.ensure_schema()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO memory_kernel_v2_records(memory_id,memory_type,scope,scope_id,content,provenance_json,version,created_at,updated_at,expires_at,status,merged_into_id,is_sensitive) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (mid, first.memory_type.value, first.scope.value, first.scope_id, merged_content, json.dumps(merged_prov, sort_keys=True, ensure_ascii=False), 1, now, now, None, "active", None, int(merged.is_sensitive)),
            )
            self._audit(conn, mid, "merge_target", 1, {"source_ids": ids})
            for source in records:
                conn.execute(
                    "UPDATE memory_kernel_v2_records SET status='merged',merged_into_id=?,updated_at=? WHERE memory_id=?",
                    (mid, now, source.memory_id),
                )
                self._audit(conn, source.memory_id, "merge_source", source.version, {"merged_into_id": mid})
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return merged

    def forget(self, memory_id: str) -> bool:
        mid = str(memory_id)
        existing = self.get(mid, include_inactive=True, include_sensitive=True)
        if existing is None:
            return False
        self._guard("memory.forget", {"memory_id": mid, "version": existing.version})
        if existing.memory_type is MemoryType.WORKING:
            with self._lock:
                return self._working.pop(mid, None) is not None
        self.ensure_schema()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            self._audit(conn, mid, "forget", existing.version, {"memory_type": existing.memory_type.value, "scope": existing.scope.value, "scope_id": existing.scope_id})
            cur = conn.execute("DELETE FROM memory_kernel_v2_records WHERE memory_id=?", (mid,))
            conn.commit()
            return cur.rowcount > 0
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def expire(self, *, now: str | None = None) -> list[str]:
        when = self._parse_time(now) if now else datetime.now(timezone.utc)
        when_text = when.isoformat(timespec="microseconds")
        expired: list[str] = []
        with self._lock:
            for mid, record in list(self._working.items()):
                if record.expires_at and self._parse_time(record.expires_at) <= when:
                    self._working[mid] = replace(record, status="expired", updated_at=when_text)
                    expired.append(mid)

        self.ensure_schema()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                "SELECT memory_id,version FROM memory_kernel_v2_records WHERE status='active' AND expires_at IS NOT NULL AND expires_at<=? ORDER BY memory_id",
                (when_text,),
            ).fetchall()
            for row in rows:
                conn.execute("UPDATE memory_kernel_v2_records SET status='expired',updated_at=? WHERE memory_id=?", (when_text, row["memory_id"]))
                self._audit(conn, row["memory_id"], "expire", int(row["version"]), {})
                expired.append(row["memory_id"])
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return sorted(set(expired))

    def audit_actions(self, memory_id: str) -> list[dict[str, Any]]:
        self.ensure_schema()
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT audit_id,memory_id,action,at,version,detail_json FROM memory_kernel_v2_audit WHERE memory_id=? ORDER BY audit_id",
                (str(memory_id),),
            ).fetchall()
        finally:
            conn.close()
        out = []
        for row in rows:
            try:
                detail = json.loads(row["detail_json"] or "{}")
            except Exception:
                detail = {}
            out.append({"audit_id": row["audit_id"], "memory_id": row["memory_id"], "action": row["action"], "at": row["at"], "version": row["version"], "detail": detail})
        return out

# === AURA v2.1 Memory Kernel R3-R1 normalized graph store BEGIN ===
# Non-destructive extension. MemoryKernelV2 remains the single canonical memory authority.
import json as _aura_v21_json
import uuid as _aura_v21_uuid
from datetime import datetime as _aura_v21_datetime, timezone as _aura_v21_timezone

_AURA_V21_R3_ORIGINAL_ENSURE_SCHEMA = MemoryKernelV2.ensure_schema

def _aura_v21_r3_now() -> str:
    return _aura_v21_datetime.now(_aura_v21_timezone.utc).isoformat(timespec="microseconds")

def _aura_v21_r3_confidence(value) -> float:
    v = float(value)
    if v < 0.0 or v > 1.0:
        raise ValueError("confidence must be between 0.0 and 1.0")
    return v

def _aura_v21_r3_json(value, default):
    if value is None:
        value = default
    return _aura_v21_json.dumps(value, sort_keys=True, ensure_ascii=False)

def _aura_v21_r3_ensure_schema(self) -> None:
    _AURA_V21_R3_ORIGINAL_ENSURE_SCHEMA(self)
    conn = self._connect()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS memory_v21_entities (
                entity_id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                canonical_name TEXT NOT NULL,
                aliases_json TEXT NOT NULL DEFAULT '[]',
                scope TEXT NOT NULL,
                scope_id TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 1.0
                    CHECK (confidence >= 0.0 AND confidence <= 1.0),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','merged','forgotten'))
            );

            CREATE INDEX IF NOT EXISTS idx_memory_v21_entities_lookup
                ON memory_v21_entities(entity_type, canonical_name, scope, scope_id, status);

            CREATE TABLE IF NOT EXISTS memory_v21_facts (
                fact_id TEXT PRIMARY KEY,
                memory_id TEXT,
                subject_entity_id TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object_text TEXT,
                object_entity_id TEXT,
                fact_key TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 1.0
                    CHECK (confidence >= 0.0 AND confidence <= 1.0),
                observed_at TEXT,
                valid_from TEXT,
                valid_to TEXT,
                provenance_json TEXT NOT NULL DEFAULT '{}',
                version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','superseded','forgotten','conflicted')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_memory_v21_facts_subject
                ON memory_v21_facts(subject_entity_id, predicate, status);
            CREATE INDEX IF NOT EXISTS idx_memory_v21_facts_key
                ON memory_v21_facts(fact_key, status);
            CREATE INDEX IF NOT EXISTS idx_memory_v21_facts_memory
                ON memory_v21_facts(memory_id, status);

            CREATE TABLE IF NOT EXISTS memory_v21_relations (
                relation_id TEXT PRIMARY KEY,
                subject_entity_id TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object_entity_id TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 1.0
                    CHECK (confidence >= 0.0 AND confidence <= 1.0),
                observed_at TEXT,
                valid_from TEXT,
                valid_to TEXT,
                provenance_json TEXT NOT NULL DEFAULT '{}',
                version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','superseded','forgotten','conflicted')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_memory_v21_relations_subject
                ON memory_v21_relations(subject_entity_id, predicate, status);
            CREATE INDEX IF NOT EXISTS idx_memory_v21_relations_object
                ON memory_v21_relations(object_entity_id, predicate, status);

            CREATE TABLE IF NOT EXISTS memory_v21_conflicts (
                conflict_id TEXT PRIMARY KEY,
                left_fact_id TEXT NOT NULL,
                right_fact_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'open'
                    CHECK (state IN ('open','resolved','dismissed')),
                resolution_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                resolved_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_memory_v21_conflicts_state
                ON memory_v21_conflicts(state, created_at);
            """
        )
        conn.commit()
    finally:
        conn.close()

def _aura_v21_r3_entity_row(row):
    if row is None:
        return None
    return {
        "entity_id": str(row["entity_id"]),
        "entity_type": str(row["entity_type"]),
        "canonical_name": str(row["canonical_name"]),
        "aliases": _aura_v21_json.loads(row["aliases_json"] or "[]"),
        "scope": str(row["scope"]),
        "scope_id": str(row["scope_id"] or ""),
        "confidence": float(row["confidence"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "status": str(row["status"]),
    }

def _aura_v21_r3_fact_row(row):
    if row is None:
        return None
    return {
        "fact_id": str(row["fact_id"]),
        "memory_id": row["memory_id"],
        "subject_entity_id": str(row["subject_entity_id"]),
        "predicate": str(row["predicate"]),
        "object_text": row["object_text"],
        "object_entity_id": row["object_entity_id"],
        "fact_key": str(row["fact_key"]),
        "confidence": float(row["confidence"]),
        "observed_at": row["observed_at"],
        "valid_from": row["valid_from"],
        "valid_to": row["valid_to"],
        "provenance": _aura_v21_json.loads(row["provenance_json"] or "{}"),
        "version": int(row["version"]),
        "status": str(row["status"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }

def _aura_v21_r3_relation_row(row):
    if row is None:
        return None
    return {
        "relation_id": str(row["relation_id"]),
        "subject_entity_id": str(row["subject_entity_id"]),
        "predicate": str(row["predicate"]),
        "object_entity_id": str(row["object_entity_id"]),
        "confidence": float(row["confidence"]),
        "observed_at": row["observed_at"],
        "valid_from": row["valid_from"],
        "valid_to": row["valid_to"],
        "provenance": _aura_v21_json.loads(row["provenance_json"] or "{}"),
        "version": int(row["version"]),
        "status": str(row["status"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }

def _aura_v21_r3_upsert_entity(
    self,
    canonical_name: str,
    *,
    entity_type: str = "concept",
    aliases=None,
    scope="user",
    scope_id=None,
    confidence: float = 1.0,
    entity_id: str | None = None,
):
    name = str(canonical_name or "").strip()
    etype = str(entity_type or "concept").strip().casefold()
    if not name:
        raise ValueError("canonical_name must not be empty")
    if not etype:
        raise ValueError("entity_type must not be empty")

    sc = self._scope(scope)
    sid = self._scope_id(sc, scope_id)
    conf = _aura_v21_r3_confidence(confidence)
    alias_values = sorted({
        str(x).strip()
        for x in (aliases or [])
        if str(x).strip()
    })
    self._guard(
        "memory.remember",
        {
            "memory_v21_operation": "entity.upsert",
            "entity_type": etype,
            "scope": sc.value,
            "scope_id": sid,
        },
    )

    now = _aura_v21_r3_now()
    conn = self._connect()
    try:
        existing = conn.execute(
            """
            SELECT * FROM memory_v21_entities
            WHERE lower(entity_type)=lower(?)
              AND lower(canonical_name)=lower(?)
              AND scope=? AND scope_id=? AND status='active'
            ORDER BY updated_at DESC LIMIT 1
            """,
            (etype, name, sc.value, sid),
        ).fetchone()

        if existing is not None:
            old_aliases = set(_aura_v21_json.loads(existing["aliases_json"] or "[]"))
            merged_aliases = sorted(old_aliases | set(alias_values))
            new_conf = max(float(existing["confidence"]), conf)
            conn.execute(
                """
                UPDATE memory_v21_entities
                SET aliases_json=?, confidence=?, updated_at=?
                WHERE entity_id=?
                """,
                (
                    _aura_v21_r3_json(merged_aliases, []),
                    new_conf,
                    now,
                    existing["entity_id"],
                ),
            )
            eid = str(existing["entity_id"])
            action = "v21.entity.upsert"
        else:
            eid = str(entity_id or _aura_v21_uuid.uuid4())
            conn.execute(
                """
                INSERT INTO memory_v21_entities(
                    entity_id, entity_type, canonical_name, aliases_json,
                    scope, scope_id, confidence, created_at, updated_at, status
                ) VALUES(?,?,?,?,?,?,?,?,?,'active')
                """,
                (
                    eid,
                    etype,
                    name,
                    _aura_v21_r3_json(alias_values, []),
                    sc.value,
                    sid,
                    conf,
                    now,
                    now,
                ),
            )
            action = "v21.entity.remember"

        self._audit(
            conn,
            eid,
            action,
            1,
            {"entity_type": etype, "scope": sc.value, "scope_id": sid},
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM memory_v21_entities WHERE entity_id=?",
            (eid,),
        ).fetchone()
        return _aura_v21_r3_entity_row(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def _aura_v21_r3_get_entity(self, entity_id: str):
    conn = self._connect()
    try:
        row = conn.execute(
            "SELECT * FROM memory_v21_entities WHERE entity_id=?",
            (str(entity_id),),
        ).fetchone()
        return _aura_v21_r3_entity_row(row)
    finally:
        conn.close()

def _aura_v21_r3_store_fact(
    self,
    subject_entity_id: str,
    predicate: str,
    *,
    object_text=None,
    object_entity_id=None,
    memory_id=None,
    fact_key=None,
    confidence: float = 1.0,
    observed_at=None,
    valid_from=None,
    valid_to=None,
    provenance=None,
    fact_id=None,
):
    subject = str(subject_entity_id or "").strip()
    pred = str(predicate or "").strip().casefold()
    obj_text = None if object_text is None else str(object_text).strip()
    obj_entity = None if object_entity_id is None else str(object_entity_id).strip()
    if not subject or not pred:
        raise ValueError("subject_entity_id and predicate are required")
    if not obj_text and not obj_entity:
        raise ValueError("fact requires object_text or object_entity_id")

    conf = _aura_v21_r3_confidence(confidence)
    key = str(
        fact_key
        or f"{subject.casefold()}|{pred}|{(obj_entity or obj_text or '').casefold()}"
    ).strip()
    if not key:
        raise ValueError("fact_key must not be empty")

    prov = dict(provenance or {})
    prov.setdefault("kernel", "MemoryKernelV2")
    prov.setdefault("schema", "aura.memory-v21.fact.v1")

    self._guard(
        "memory.remember",
        {"memory_v21_operation": "fact.store", "fact_key": key},
    )
    now = _aura_v21_r3_now()
    conn = self._connect()
    try:
        existing = conn.execute(
            """
            SELECT * FROM memory_v21_facts
            WHERE fact_key=? AND status='active'
            ORDER BY version DESC, updated_at DESC LIMIT 1
            """,
            (key,),
        ).fetchone()

        if existing is not None:
            fid = str(existing["fact_id"])
            version = int(existing["version"]) + 1
            conn.execute(
                """
                UPDATE memory_v21_facts
                SET memory_id=?, subject_entity_id=?, predicate=?,
                    object_text=?, object_entity_id=?, confidence=?,
                    observed_at=?, valid_from=?, valid_to=?, provenance_json=?,
                    version=?, updated_at=?
                WHERE fact_id=?
                """,
                (
                    memory_id,
                    subject,
                    pred,
                    obj_text,
                    obj_entity,
                    conf,
                    observed_at,
                    valid_from,
                    valid_to,
                    _aura_v21_r3_json(prov, {}),
                    version,
                    now,
                    fid,
                ),
            )
            action = "v21.fact.update"
        else:
            fid = str(fact_id or _aura_v21_uuid.uuid4())
            version = 1
            conn.execute(
                """
                INSERT INTO memory_v21_facts(
                    fact_id, memory_id, subject_entity_id, predicate,
                    object_text, object_entity_id, fact_key, confidence,
                    observed_at, valid_from, valid_to, provenance_json,
                    version, status, created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'active',?,?)
                """,
                (
                    fid,
                    memory_id,
                    subject,
                    pred,
                    obj_text,
                    obj_entity,
                    key,
                    conf,
                    observed_at,
                    valid_from,
                    valid_to,
                    _aura_v21_r3_json(prov, {}),
                    version,
                    now,
                    now,
                ),
            )
            action = "v21.fact.remember"

        self._audit(
            conn,
            fid,
            action,
            version,
            {"fact_key": key, "predicate": pred},
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM memory_v21_facts WHERE fact_id=?",
            (fid,),
        ).fetchone()
        return _aura_v21_r3_fact_row(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def _aura_v21_r3_list_facts(
    self,
    *,
    subject_entity_id=None,
    predicate=None,
    status="active",
    limit: int = 100,
):
    clauses = ["status=?"]
    params = [str(status)]
    if subject_entity_id is not None:
        clauses.append("subject_entity_id=?")
        params.append(str(subject_entity_id))
    if predicate is not None:
        clauses.append("predicate=?")
        params.append(str(predicate).strip().casefold())
    params.append(max(1, min(int(limit), 500)))
    conn = self._connect()
    try:
        rows = conn.execute(
            "SELECT * FROM memory_v21_facts WHERE "
            + " AND ".join(clauses)
            + " ORDER BY updated_at DESC LIMIT ?",
            tuple(params),
        ).fetchall()
        return [_aura_v21_r3_fact_row(r) for r in rows]
    finally:
        conn.close()

def _aura_v21_r3_store_relation(
    self,
    subject_entity_id: str,
    predicate: str,
    object_entity_id: str,
    *,
    confidence: float = 1.0,
    observed_at=None,
    valid_from=None,
    valid_to=None,
    provenance=None,
    relation_id=None,
):
    subject = str(subject_entity_id or "").strip()
    pred = str(predicate or "").strip().casefold()
    obj = str(object_entity_id or "").strip()
    if not subject or not pred or not obj:
        raise ValueError("subject_entity_id, predicate and object_entity_id are required")

    conf = _aura_v21_r3_confidence(confidence)
    prov = dict(provenance or {})
    prov.setdefault("kernel", "MemoryKernelV2")
    prov.setdefault("schema", "aura.memory-v21.relation.v1")
    self._guard(
        "memory.remember",
        {"memory_v21_operation": "relation.store", "predicate": pred},
    )

    now = _aura_v21_r3_now()
    conn = self._connect()
    try:
        existing = conn.execute(
            """
            SELECT * FROM memory_v21_relations
            WHERE subject_entity_id=? AND predicate=? AND object_entity_id=?
              AND status='active'
            ORDER BY version DESC, updated_at DESC LIMIT 1
            """,
            (subject, pred, obj),
        ).fetchone()

        if existing is not None:
            rid = str(existing["relation_id"])
            version = int(existing["version"]) + 1
            conn.execute(
                """
                UPDATE memory_v21_relations
                SET confidence=?, observed_at=?, valid_from=?, valid_to=?,
                    provenance_json=?, version=?, updated_at=?
                WHERE relation_id=?
                """,
                (
                    conf,
                    observed_at,
                    valid_from,
                    valid_to,
                    _aura_v21_r3_json(prov, {}),
                    version,
                    now,
                    rid,
                ),
            )
            action = "v21.relation.update"
        else:
            rid = str(relation_id or _aura_v21_uuid.uuid4())
            version = 1
            conn.execute(
                """
                INSERT INTO memory_v21_relations(
                    relation_id, subject_entity_id, predicate, object_entity_id,
                    confidence, observed_at, valid_from, valid_to,
                    provenance_json, version, status, created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,'active',?,?)
                """,
                (
                    rid,
                    subject,
                    pred,
                    obj,
                    conf,
                    observed_at,
                    valid_from,
                    valid_to,
                    _aura_v21_r3_json(prov, {}),
                    version,
                    now,
                    now,
                ),
            )
            action = "v21.relation.remember"

        self._audit(
            conn,
            rid,
            action,
            version,
            {
                "predicate": pred,
                "subject_entity_id": subject,
                "object_entity_id": obj,
            },
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM memory_v21_relations WHERE relation_id=?",
            (rid,),
        ).fetchone()
        return _aura_v21_r3_relation_row(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def _aura_v21_r3_list_relations(
    self,
    *,
    subject_entity_id=None,
    object_entity_id=None,
    predicate=None,
    status="active",
    limit: int = 100,
):
    clauses = ["status=?"]
    params = [str(status)]
    if subject_entity_id is not None:
        clauses.append("subject_entity_id=?")
        params.append(str(subject_entity_id))
    if object_entity_id is not None:
        clauses.append("object_entity_id=?")
        params.append(str(object_entity_id))
    if predicate is not None:
        clauses.append("predicate=?")
        params.append(str(predicate).strip().casefold())
    params.append(max(1, min(int(limit), 500)))
    conn = self._connect()
    try:
        rows = conn.execute(
            "SELECT * FROM memory_v21_relations WHERE "
            + " AND ".join(clauses)
            + " ORDER BY updated_at DESC LIMIT ?",
            tuple(params),
        ).fetchall()
        return [_aura_v21_r3_relation_row(r) for r in rows]
    finally:
        conn.close()

MemoryKernelV2.ensure_schema = _aura_v21_r3_ensure_schema
MemoryKernelV2.v21_upsert_entity = _aura_v21_r3_upsert_entity
MemoryKernelV2.v21_get_entity = _aura_v21_r3_get_entity
MemoryKernelV2.v21_store_fact = _aura_v21_r3_store_fact
MemoryKernelV2.v21_list_facts = _aura_v21_r3_list_facts
MemoryKernelV2.v21_store_relation = _aura_v21_r3_store_relation
MemoryKernelV2.v21_list_relations = _aura_v21_r3_list_relations
# === AURA v2.1 Memory Kernel R3-R1 normalized graph store END ===

# === AURA v2.1 Memory Kernel R4 - temporal semantics + conflict ledger BEGIN ===
# Extends the canonical MemoryKernelV2 only. R3 graph-store authority is preserved.
from datetime import datetime as _aura_v21_r4_datetime, timezone as _aura_v21_r4_timezone
import json as _aura_v21_r4_json
import uuid as _aura_v21_r4_uuid

def _aura_v21_r4_parse_time(self, value):
    if value is None or str(value).strip() == "":
        return None
    parsed = self._parse_time(str(value))
    if parsed is None:
        raise ValueError(f"invalid timestamp: {value!r}")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_aura_v21_r4_timezone.utc)
    return parsed.astimezone(_aura_v21_r4_timezone.utc)

def _aura_v21_r4_iso(self, value):
    parsed = _aura_v21_r4_parse_time(self, value)
    return parsed.isoformat(timespec="microseconds") if parsed is not None else None

def _aura_v21_r4_validate_temporal(
    self,
    *,
    observed_at=None,
    valid_from=None,
    valid_to=None,
):
    observed = _aura_v21_r4_parse_time(self, observed_at)
    start = _aura_v21_r4_parse_time(self, valid_from)
    end = _aura_v21_r4_parse_time(self, valid_to)
    if start is not None and end is not None and end < start:
        raise ValueError("valid_to must be greater than or equal to valid_from")
    return {
        "observed_at": observed.isoformat(timespec="microseconds") if observed else None,
        "valid_from": start.isoformat(timespec="microseconds") if start else None,
        "valid_to": end.isoformat(timespec="microseconds") if end else None,
    }

def _aura_v21_r4_temporal_overlap(
    self,
    left_valid_from=None,
    left_valid_to=None,
    right_valid_from=None,
    right_valid_to=None,
):
    lf = _aura_v21_r4_parse_time(self, left_valid_from)
    lt = _aura_v21_r4_parse_time(self, left_valid_to)
    rf = _aura_v21_r4_parse_time(self, right_valid_from)
    rt = _aura_v21_r4_parse_time(self, right_valid_to)

    if lf is not None and lt is not None and lt < lf:
        raise ValueError("left temporal interval is invalid")
    if rf is not None and rt is not None and rt < rf:
        raise ValueError("right temporal interval is invalid")

    if lt is not None and rf is not None and lt < rf:
        return False
    if rt is not None and lf is not None and rt < lf:
        return False
    return True

def _aura_v21_r4_fact_object_identity(row):
    if row["object_entity_id"] is not None:
        return ("entity", str(row["object_entity_id"]).casefold())
    return ("text", str(row["object_text"] or "").strip().casefold())

def _aura_v21_r4_fact_row_by_id(self, fact_id):
    conn = self._connect()
    try:
        row = conn.execute(
            "SELECT * FROM memory_v21_facts WHERE fact_id=?",
            (str(fact_id),),
        ).fetchone()
        return _aura_v21_r3_fact_row(row)
    finally:
        conn.close()

def _aura_v21_r4_fact_is_valid_at(self, fact, at=None):
    if not fact:
        return False
    if str(fact.get("status") or "") != "active":
        return False
    when = _aura_v21_r4_parse_time(
        self,
        at or _aura_v21_r4_datetime.now(_aura_v21_r4_timezone.utc).isoformat(),
    )
    start = _aura_v21_r4_parse_time(self, fact.get("valid_from"))
    end = _aura_v21_r4_parse_time(self, fact.get("valid_to"))
    if start is not None and when < start:
        return False
    if end is not None and when > end:
        return False
    return True

def _aura_v21_r4_list_facts_at(
    self,
    *,
    subject_entity_id=None,
    predicate=None,
    at=None,
    limit=100,
):
    rows = self.v21_list_facts(
        subject_entity_id=subject_entity_id,
        predicate=predicate,
        status="active",
        limit=max(1, min(int(limit) * 4, 500)),
    )
    filtered = [
        row for row in rows
        if _aura_v21_r4_fact_is_valid_at(self, row, at=at)
    ]
    return filtered[:max(1, min(int(limit), 500))]

def _aura_v21_r4_conflict_row(row):
    if row is None:
        return None
    return {
        "conflict_id": str(row["conflict_id"]),
        "left_fact_id": str(row["left_fact_id"]),
        "right_fact_id": str(row["right_fact_id"]),
        "reason": str(row["reason"]),
        "state": str(row["state"]),
        "resolution": _aura_v21_r4_json.loads(row["resolution_json"] or "{}"),
        "created_at": str(row["created_at"]),
        "resolved_at": row["resolved_at"],
    }

def _aura_v21_r4_open_conflict(
    self,
    left_fact_id,
    right_fact_id,
    *,
    reason="contradictory_temporal_fact",
):
    left_id = str(left_fact_id or "").strip()
    right_id = str(right_fact_id or "").strip()
    if not left_id or not right_id:
        raise ValueError("left_fact_id and right_fact_id are required")
    if left_id == right_id:
        raise ValueError("a fact cannot conflict with itself")

    self._guard(
        "memory.update",
        {
            "memory_v21_operation": "conflict.open",
            "left_fact_id": left_id,
            "right_fact_id": right_id,
        },
    )

    now = _aura_v21_r3_now()
    conn = self._connect()
    try:
        left = conn.execute(
            "SELECT fact_id FROM memory_v21_facts WHERE fact_id=?",
            (left_id,),
        ).fetchone()
        right = conn.execute(
            "SELECT fact_id FROM memory_v21_facts WHERE fact_id=?",
            (right_id,),
        ).fetchone()
        if left is None or right is None:
            raise KeyError("conflict facts must both exist")

        existing = conn.execute(
            """
            SELECT * FROM memory_v21_conflicts
            WHERE state='open'
              AND (
                    (left_fact_id=? AND right_fact_id=?)
                 OR (left_fact_id=? AND right_fact_id=?)
              )
            ORDER BY created_at DESC LIMIT 1
            """,
            (left_id, right_id, right_id, left_id),
        ).fetchone()
        if existing is not None:
            return _aura_v21_r4_conflict_row(existing)

        conflict_id = str(_aura_v21_r4_uuid.uuid4())
        conn.execute(
            """
            INSERT INTO memory_v21_conflicts(
                conflict_id, left_fact_id, right_fact_id, reason,
                state, resolution_json, created_at, resolved_at
            ) VALUES(?,?,?,?,'open','{}',?,NULL)
            """,
            (conflict_id, left_id, right_id, str(reason or "contradictory_temporal_fact"), now),
        )
        self._audit(
            conn,
            conflict_id,
            "v21.conflict.open",
            1,
            {
                "left_fact_id": left_id,
                "right_fact_id": right_id,
                "reason": str(reason or "contradictory_temporal_fact"),
            },
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM memory_v21_conflicts WHERE conflict_id=?",
            (conflict_id,),
        ).fetchone()
        return _aura_v21_r4_conflict_row(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def _aura_v21_r4_list_conflicts(self, *, state="open", limit=100):
    state_value = str(state or "open").strip().casefold()
    if state_value not in {"open", "resolved", "dismissed"}:
        raise ValueError("state must be open, resolved or dismissed")
    conn = self._connect()
    try:
        rows = conn.execute(
            """
            SELECT * FROM memory_v21_conflicts
            WHERE state=?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (state_value, max(1, min(int(limit), 500))),
        ).fetchall()
        return [_aura_v21_r4_conflict_row(r) for r in rows]
    finally:
        conn.close()

def _aura_v21_r4_detect_fact_conflicts(self, fact_id):
    fid = str(fact_id or "").strip()
    conn = self._connect()
    try:
        current = conn.execute(
            "SELECT * FROM memory_v21_facts WHERE fact_id=?",
            (fid,),
        ).fetchone()
        if current is None:
            raise KeyError(fid)
        if str(current["status"]) != "active":
            return []

        candidates = conn.execute(
            """
            SELECT * FROM memory_v21_facts
            WHERE subject_entity_id=?
              AND predicate=?
              AND fact_id<>?
              AND status='active'
            ORDER BY updated_at DESC
            """,
            (current["subject_entity_id"], current["predicate"], fid),
        ).fetchall()
    finally:
        conn.close()

    opened = []
    current_obj = _aura_v21_r4_fact_object_identity(current)

    for other in candidates:
        if _aura_v21_r4_fact_object_identity(other) == current_obj:
            continue
        if not _aura_v21_r4_temporal_overlap(
            self,
            current["valid_from"], current["valid_to"],
            other["valid_from"], other["valid_to"],
        ):
            continue
        opened.append(
            _aura_v21_r4_open_conflict(
                self,
                str(other["fact_id"]),
                fid,
                reason="same_subject_predicate_different_object_overlapping_validity",
            )
        )
    return opened

def _aura_v21_r4_store_temporal_fact(
    self,
    subject_entity_id,
    predicate,
    *,
    object_text=None,
    object_entity_id=None,
    memory_id=None,
    fact_key=None,
    confidence=1.0,
    observed_at=None,
    valid_from=None,
    valid_to=None,
    provenance=None,
    fact_id=None,
    detect_conflicts=True,
):
    temporal = _aura_v21_r4_validate_temporal(
        self,
        observed_at=observed_at,
        valid_from=valid_from,
        valid_to=valid_to,
    )
    fact = self.v21_store_fact(
        subject_entity_id,
        predicate,
        object_text=object_text,
        object_entity_id=object_entity_id,
        memory_id=memory_id,
        fact_key=fact_key,
        confidence=confidence,
        observed_at=temporal["observed_at"],
        valid_from=temporal["valid_from"],
        valid_to=temporal["valid_to"],
        provenance=provenance,
        fact_id=fact_id,
    )
    conflicts = (
        _aura_v21_r4_detect_fact_conflicts(self, fact["fact_id"])
        if detect_conflicts else []
    )
    return {
        "fact": fact,
        "conflicts": conflicts,
    }

def _aura_v21_r4_resolve_conflict(
    self,
    conflict_id,
    *,
    resolution,
    note=None,
):
    cid = str(conflict_id or "").strip()
    choice = str(resolution or "").strip().casefold()
    allowed = {"keep_left", "keep_right", "keep_both", "dismiss"}
    if choice not in allowed:
        raise ValueError("resolution must be keep_left, keep_right, keep_both or dismiss")

    self._guard(
        "memory.update",
        {
            "memory_v21_operation": "conflict.resolve",
            "conflict_id": cid,
            "resolution": choice,
        },
    )

    now = _aura_v21_r3_now()
    conn = self._connect()
    try:
        row = conn.execute(
            "SELECT * FROM memory_v21_conflicts WHERE conflict_id=?",
            (cid,),
        ).fetchone()
        if row is None:
            raise KeyError(cid)

        if str(row["state"]) != "open":
            return _aura_v21_r4_conflict_row(row)

        left_id = str(row["left_fact_id"])
        right_id = str(row["right_fact_id"])
        state = "dismissed" if choice == "dismiss" else "resolved"

        if choice == "keep_left":
            conn.execute(
                "UPDATE memory_v21_facts SET status='superseded', updated_at=? WHERE fact_id=? AND status='active'",
                (now, right_id),
            )
        elif choice == "keep_right":
            conn.execute(
                "UPDATE memory_v21_facts SET status='superseded', updated_at=? WHERE fact_id=? AND status='active'",
                (now, left_id),
            )

        resolution_json = {
            "resolution": choice,
            "note": None if note is None else str(note),
            "left_fact_id": left_id,
            "right_fact_id": right_id,
        }
        conn.execute(
            """
            UPDATE memory_v21_conflicts
            SET state=?, resolution_json=?, resolved_at=?
            WHERE conflict_id=?
            """,
            (
                state,
                _aura_v21_r4_json.dumps(resolution_json, sort_keys=True, ensure_ascii=False),
                now,
                cid,
            ),
        )
        self._audit(
            conn,
            cid,
            "v21.conflict.resolve",
            1,
            resolution_json,
        )
        conn.commit()
        resolved = conn.execute(
            "SELECT * FROM memory_v21_conflicts WHERE conflict_id=?",
            (cid,),
        ).fetchone()
        return _aura_v21_r4_conflict_row(resolved)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

MemoryKernelV2.v21_validate_temporal = _aura_v21_r4_validate_temporal
MemoryKernelV2.v21_temporal_overlap = _aura_v21_r4_temporal_overlap
MemoryKernelV2.v21_fact_by_id = _aura_v21_r4_fact_row_by_id
MemoryKernelV2.v21_fact_is_valid_at = _aura_v21_r4_fact_is_valid_at
MemoryKernelV2.v21_list_facts_at = _aura_v21_r4_list_facts_at
MemoryKernelV2.v21_open_conflict = _aura_v21_r4_open_conflict
MemoryKernelV2.v21_list_conflicts = _aura_v21_r4_list_conflicts
MemoryKernelV2.v21_detect_fact_conflicts = _aura_v21_r4_detect_fact_conflicts
MemoryKernelV2.v21_store_temporal_fact = _aura_v21_r4_store_temporal_fact
MemoryKernelV2.v21_resolve_conflict = _aura_v21_r4_resolve_conflict
# === AURA v2.1 Memory Kernel R4 - temporal semantics + conflict ledger END ===

# === AURA v2.1 Memory Kernel R5 - explainable recall graph BEGIN ===
# Goal: deterministic, scope-safe, temporal, conflict-aware, explainable graph recall.
import math as _aura_v21_r5_math
import re as _aura_v21_r5_re
import unicodedata as _aura_v21_r5_unicodedata
from datetime import datetime as _aura_v21_r5_datetime, timezone as _aura_v21_r5_timezone

_AURA_V21_R5_STOPWORDS = frozenset({
    "a","ai","au","aux","avec","ce","ces","dans","de","des","du","elle","en","et",
    "eux","il","je","la","le","les","leur","lui","ma","mais","me","meme","mes","moi",
    "mon","ne","nos","notre","nous","on","ou","par","pas","pour","qu","que","qui",
    "sa","se","ses","son","sur","ta","te","tes","toi","ton","tu","un","une","vos",
    "votre","vous","the","a","an","and","or","of","to","in","on","for","with","is",
    "are","was","were","be","been","this","that","these","those","my","your","our",
})

def _aura_v21_r5_normalize_text(value):
    text = str(value or "").strip().casefold()
    text = _aura_v21_r5_unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not _aura_v21_r5_unicodedata.combining(ch))
    text = _aura_v21_r5_re.sub(r"[^a-z0-9_+-]+", " ", text)
    return " ".join(text.split())

def _aura_v21_r5_tokens(value):
    return {
        token for token in _aura_v21_r5_normalize_text(value).split()
        if len(token) >= 2 and token not in _AURA_V21_R5_STOPWORDS
    }

def _aura_v21_r5_scope_rank(
    self,
    entity_scope,
    entity_scope_id,
    *,
    scope,
    scope_id,
    allow_user_fallback=True,
):
    requested = self._scope(scope)
    requested_id = self._scope_id(requested, scope_id)
    e_scope = str(entity_scope or "")
    e_id = str(entity_scope_id or "")

    if e_scope == requested.value and e_id == requested_id:
        return {"allowed": True, "rank": 1.0, "reason": "exact_scope"}

    if allow_user_fallback and requested.value in {"project", "session"}:
        if e_scope == "user" and e_id == "default":
            return {"allowed": True, "rank": 0.72, "reason": "user_fallback"}

    return {"allowed": False, "rank": 0.0, "reason": "scope_mismatch"}

def _aura_v21_r5_open_conflict_ids(self):
    conn = self._connect()
    try:
        rows = conn.execute(
            """
            SELECT left_fact_id, right_fact_id
            FROM memory_v21_conflicts
            WHERE state='open'
            """
        ).fetchall()
        ids = set()
        for row in rows:
            ids.add(str(row["left_fact_id"]))
            ids.add(str(row["right_fact_id"]))
        return ids
    finally:
        conn.close()

def _aura_v21_r5_sensitive_fact_ids(self):
    conn = self._connect()
    try:
        rows = conn.execute(
            """
            SELECT f.fact_id
            FROM memory_v21_facts f
            JOIN memory_kernel_v2_records m ON m.memory_id=f.memory_id
            WHERE f.memory_id IS NOT NULL AND m.is_sensitive=1
            """
        ).fetchall()
        return {str(row["fact_id"]) for row in rows}
    finally:
        conn.close()

def _aura_v21_r5_entity_rows(self):
    conn = self._connect()
    try:
        rows = conn.execute(
            """
            SELECT * FROM memory_v21_entities
            WHERE status='active'
            ORDER BY updated_at DESC, entity_id ASC
            """
        ).fetchall()
        result = []
        for row in rows:
            result.append({
                "entity_id": str(row["entity_id"]),
                "entity_type": str(row["entity_type"]),
                "canonical_name": str(row["canonical_name"]),
                "aliases": _aura_v21_json.loads(row["aliases_json"] or "[]"),
                "scope": str(row["scope"]),
                "scope_id": str(row["scope_id"] or ""),
                "confidence": float(row["confidence"]),
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
                "status": str(row["status"]),
            })
        return result
    finally:
        conn.close()

def _aura_v21_r5_relation_rows(self):
    return self.v21_list_relations(status="active", limit=500)

def _aura_v21_r5_score_fact(
    self,
    fact,
    entity,
    query_tokens,
    *,
    scope_rank,
    at=None,
    relation_boost=0.0,
    conflict_open=False,
):
    predicate_tokens = _aura_v21_r5_tokens(fact.get("predicate"))
    object_tokens = _aura_v21_r5_tokens(
        fact.get("object_text") or fact.get("object_entity_id") or ""
    )
    entity_tokens = _aura_v21_r5_tokens(
        " ".join(
            [entity.get("canonical_name", "")]
            + list(entity.get("aliases") or [])
            + [entity.get("entity_type", "")]
        )
    )
    searchable = predicate_tokens | object_tokens | entity_tokens

    if query_tokens:
        overlap = query_tokens & searchable
        lexical = len(overlap) / max(1, len(query_tokens))
    else:
        overlap = set()
        lexical = 0.0

    confidence = max(0.0, min(1.0, float(fact.get("confidence") or 0.0)))
    entity_conf = max(0.0, min(1.0, float(entity.get("confidence") or 0.0)))
    temporal = 1.0 if self.v21_fact_is_valid_at(fact, at=at) else 0.0

    conflict_penalty = 0.18 if conflict_open else 0.0
    base = (
        lexical * 0.48
        + scope_rank * 0.20
        + confidence * 0.14
        + entity_conf * 0.06
        + temporal * 0.08
        + min(max(float(relation_boost), 0.0), 1.0) * 0.12
        - conflict_penalty
    )
    score = max(0.0, min(1.0, base))

    return {
        "score": round(score, 6),
        "components": {
            "lexical": round(lexical, 6),
            "scope": round(scope_rank, 6),
            "fact_confidence": round(confidence, 6),
            "entity_confidence": round(entity_conf, 6),
            "temporal_valid": round(temporal, 6),
            "relation_boost": round(float(relation_boost), 6),
            "open_conflict_penalty": round(conflict_penalty, 6),
        },
        "matched_tokens": sorted(overlap),
    }

def _aura_v21_r5_relation_neighbors(self, seed_ids, entity_by_id, allowed_entity_ids):
    rows = self.v21_list_relations(status="active", limit=500)
    neighbors = {}
    for row in rows:
        s = str(row["subject_entity_id"])
        o = str(row["object_entity_id"])
        if s in seed_ids and o in allowed_entity_ids:
            neighbors.setdefault(o, []).append(row)
        if o in seed_ids and s in allowed_entity_ids:
            neighbors.setdefault(s, []).append(row)
    return neighbors

def _aura_v21_r5_recall_graph(
    self,
    query,
    *,
    scope="user",
    scope_id=None,
    at=None,
    limit=10,
    allow_user_fallback=True,
    max_relation_hops=1,
    include_sensitive=False,
    min_score=0.12,
):
    query_text = str(query or "").strip()
    query_tokens = _aura_v21_r5_tokens(query_text)
    requested_scope = self._scope(scope)
    requested_scope_id = self._scope_id(requested_scope, scope_id)
    at_value = at or _aura_v21_r5_datetime.now(_aura_v21_r5_timezone.utc).isoformat()

    entities = self.v21_entity_rows()
    entity_by_id = {row["entity_id"]: row for row in entities}

    allowed_entities = {}
    for row in entities:
        sr = self.v21_scope_rank(
            row["scope"],
            row["scope_id"],
            scope=requested_scope,
            scope_id=requested_scope_id,
            allow_user_fallback=allow_user_fallback,
        )
        if sr["allowed"]:
            allowed_entities[row["entity_id"]] = {
                "entity": row,
                "scope_rank": sr["rank"],
                "scope_reason": sr["reason"],
            }

    # Seed entities are lexical matches to the query.
    seed_ids = set()
    for eid, info in allowed_entities.items():
        row = info["entity"]
        etokens = _aura_v21_r5_tokens(
            " ".join(
                [row["canonical_name"]]
                + list(row.get("aliases") or [])
                + [row["entity_type"]]
            )
        )
        if query_tokens & etokens:
            seed_ids.add(eid)

    relation_neighbors = {}
    if int(max_relation_hops) >= 1 and seed_ids:
        relation_neighbors = self.v21_relation_neighbors(
            seed_ids,
            entity_by_id,
            set(allowed_entities),
        )

    open_conflict_ids = self.v21_open_conflict_ids()
    sensitive_ids = set() if include_sensitive else self.v21_sensitive_fact_ids()

    candidates = []
    for eid, info in allowed_entities.items():
        entity = info["entity"]
        relation_boost = 0.0
        relation_evidence = []

        if eid in seed_ids:
            relation_boost = 0.25
        elif eid in relation_neighbors:
            relation_boost = min(
                1.0,
                max(float(r.get("confidence") or 0.0) for r in relation_neighbors[eid])
            )
            relation_evidence = [
                {
                    "relation_id": r["relation_id"],
                    "predicate": r["predicate"],
                    "subject_entity_id": r["subject_entity_id"],
                    "object_entity_id": r["object_entity_id"],
                    "confidence": r["confidence"],
                }
                for r in relation_neighbors[eid]
            ]

        facts = self.v21_list_facts(
            subject_entity_id=eid,
            status="active",
            limit=500,
        )

        for fact in facts:
            if fact["fact_id"] in sensitive_ids:
                continue
            if not self.v21_fact_is_valid_at(fact, at=at_value):
                continue

            scored = self.v21_score_fact(
                fact,
                entity,
                query_tokens,
                scope_rank=info["scope_rank"],
                at=at_value,
                relation_boost=relation_boost,
                conflict_open=fact["fact_id"] in open_conflict_ids,
            )
            if scored["score"] < float(min_score):
                continue

            candidates.append({
                "kind": "fact",
                "fact": fact,
                "entity": entity,
                "score": scored["score"],
                "score_components": scored["components"],
                "matched_tokens": scored["matched_tokens"],
                "scope_reason": info["scope_reason"],
                "open_conflict": fact["fact_id"] in open_conflict_ids,
                "relation_evidence": relation_evidence,
                "why": {
                    "scope": info["scope_reason"],
                    "temporal": f"valid_at:{at_value}",
                    "confidence": fact["confidence"],
                    "matched_tokens": scored["matched_tokens"],
                    "via_relation": bool(relation_evidence),
                    "open_conflict": fact["fact_id"] in open_conflict_ids,
                },
            })

    # Strong deterministic tie-breaking: score desc, confidence desc, updated_at desc, fact_id asc.
    candidates.sort(
        key=lambda row: (
            -float(row["score"]),
            -float(row["fact"].get("confidence") or 0.0),
            str(row["fact"].get("updated_at") or ""),
            str(row["fact"].get("fact_id") or ""),
        )
    )

    selected = candidates[:max(1, min(int(limit), 100))]

    return {
        "schema": "aura.memory-v21.recall-graph.v1",
        "query": query_text,
        "query_tokens": sorted(query_tokens),
        "scope": requested_scope.value,
        "scope_id": requested_scope_id,
        "at": at_value,
        "include_sensitive": bool(include_sensitive),
        "allow_user_fallback": bool(allow_user_fallback),
        "max_relation_hops": int(max_relation_hops),
        "candidate_count": len(candidates),
        "count": len(selected),
        "results": selected,
    }

def _aura_v21_r5_explain_recall(self, recall_result):
    if not isinstance(recall_result, dict):
        raise TypeError("recall_result must be a dict")
    explanation = []
    for index, row in enumerate(recall_result.get("results") or [], 1):
        fact = row.get("fact") or {}
        entity = row.get("entity") or {}
        explanation.append({
            "rank": index,
            "score": row.get("score"),
            "entity": entity.get("canonical_name"),
            "predicate": fact.get("predicate"),
            "object": fact.get("object_text") or fact.get("object_entity_id"),
            "scope_reason": row.get("scope_reason"),
            "open_conflict": bool(row.get("open_conflict")),
            "matched_tokens": list(row.get("matched_tokens") or []),
            "score_components": dict(row.get("score_components") or {}),
            "relation_count": len(row.get("relation_evidence") or []),
        })
    return explanation

MemoryKernelV2.v21_normalize_text = staticmethod(_aura_v21_r5_normalize_text)
MemoryKernelV2.v21_tokens = staticmethod(_aura_v21_r5_tokens)
MemoryKernelV2.v21_scope_rank = _aura_v21_r5_scope_rank
MemoryKernelV2.v21_open_conflict_ids = _aura_v21_r5_open_conflict_ids
MemoryKernelV2.v21_sensitive_fact_ids = _aura_v21_r5_sensitive_fact_ids
MemoryKernelV2.v21_entity_rows = _aura_v21_r5_entity_rows
MemoryKernelV2.v21_relation_rows = _aura_v21_r5_relation_rows
MemoryKernelV2.v21_score_fact = _aura_v21_r5_score_fact
MemoryKernelV2.v21_relation_neighbors = _aura_v21_r5_relation_neighbors
MemoryKernelV2.v21_recall_graph = _aura_v21_r5_recall_graph
MemoryKernelV2.v21_explain_recall = _aura_v21_r5_explain_recall
# === AURA v2.1 Memory Kernel R5 - explainable recall graph END ===
