"""Pure, read-only planning primitives for future Legacy memory migration.
No destination repository or real-state access is present in this module.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime
import hashlib, json, sqlite3
from pathlib import Path

MIGRATION_VERSION = "legacy_memory_to_native_v1"

@dataclass(frozen=True)
class LegacyMemoryRecord:
    legacy_id: int | str
    content: str | None
    memory_type: str | None = "fact"
    importance: int | None = 1
    confidence: float | None = 1.0
    source: str | None = "legacy"
    created_at: str | None = None
    updated_at: str | None = None
    status: str | None = "ACTIVE"
    is_sensitive: bool = False
    scope: str | None = "user"
    scope_id: str | None = "default"

@dataclass(frozen=True)
class MigrationCandidate:
    classification: str
    legacy_id: str
    native_content: str = ""
    native_memory_type: str = ""
    native_scope: str = ""
    native_scope_id: str = ""
    native_source: str = "legacy_aura"
    confidence: float | None = None
    importance: int | None = None
    created_at: str | None = None
    updated_at: str | None = None
    fingerprint: str = ""
    reason: str = ""
    migration_version: str = MIGRATION_VERSION

@dataclass(frozen=True)
class DryRunResult:
    source_records: int = 0; eligible: int = 0; new: int = 0
    already_migrated: int = 0; possible_duplicates: int = 0; conflicts: int = 0
    invalid: int = 0; unsupported: int = 0; would_insert: int = 0
    would_update: int = 0; would_skip: int = 0
    candidates: tuple[MigrationCandidate, ...] = ()

_TYPE_MAP = {"fact":"fact", "preference":"preference", "project":"project", "goal":"goal", "habit":"habit", "note":"note"}

def fingerprint(record: LegacyMemoryRecord) -> str:
    structural = {"id":str(record.legacy_id),"content":str(record.content or ""),"type":str(record.memory_type or ""),"created_at":str(record.created_at or "")}
    return hashlib.sha256(json.dumps(structural, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def _candidate(record: LegacyMemoryRecord) -> MigrationCandidate:
    lid=str(record.legacy_id)
    if not lid or record.content is None or not str(record.content).strip():
        return MigrationCandidate("INVALID",lid,reason="empty_content_or_id",fingerprint=fingerprint(record))
    status=str(record.status or "ACTIVE").upper()
    if status not in {"ACTIVE", "ENABLED"}:
        return MigrationCandidate("UNSUPPORTED",lid,reason="deleted_or_inactive",fingerprint=fingerprint(record))
    typ=str(record.memory_type or "").strip().lower()
    if typ not in _TYPE_MAP:
        return MigrationCandidate("UNSUPPORTED",lid,reason="unknown_memory_type",fingerprint=fingerprint(record))
    scope=str(record.scope or "user").strip().lower(); scope_id=str(record.scope_id or "default").strip()
    if scope != "user" or scope_id != "default":
        return MigrationCandidate("UNSUPPORTED",lid,reason="ambiguous_legacy_scope",fingerprint=fingerprint(record))
    confidence=None if record.confidence is None else float(record.confidence)
    if confidence is not None and not 0.0 <= confidence <= 1.0:
        return MigrationCandidate("INVALID",lid,reason="confidence_out_of_range",fingerprint=fingerprint(record))
    return MigrationCandidate("NEW",lid,str(record.content).strip(),_TYPE_MAP[typ],"user","default","legacy_aura",confidence, max(1,min(5,int(record.importance or 1))), record.created_at,record.updated_at or record.created_at, fingerprint(record))

def plan(records, *, migrated_legacy_ids=(), native_fingerprints=(), native_contents=()) -> DryRunResult:
    migrated={str(x) for x in migrated_legacy_ids}; fps={str(x) for x in native_fingerprints}; contents={str(x).strip() for x in native_contents}
    out=[]; counts={k:0 for k in ('eligible','new','already_migrated','possible_duplicates','conflicts','invalid','unsupported','would_insert','would_update','would_skip')}
    seen=set()
    rows=list(records)
    for raw in rows:
        r=raw if isinstance(raw,LegacyMemoryRecord) else LegacyMemoryRecord(**raw)
        c=_candidate(r)
        if c.classification == 'NEW':
            counts['eligible']+=1
            if c.legacy_id in migrated: c=MigrationCandidate(**{**asdict(c),'classification':'ALREADY_MIGRATED','reason':'legacy_provenance_exists'}); counts['already_migrated']+=1; counts['would_skip']+=1
            elif c.fingerprint in fps: c=MigrationCandidate(**{**asdict(c),'classification':'ALREADY_MIGRATED','reason':'fingerprint_exists'}); counts['already_migrated']+=1; counts['would_skip']+=1
            elif c.native_content in contents or c.native_content in seen: c=MigrationCandidate(**{**asdict(c),'classification':'POSSIBLE_DUPLICATE','reason':'semantic_duplicate_requires_review'}); counts['possible_duplicates']+=1; counts['would_skip']+=1
            else: counts['new']+=1; counts['would_insert']+=1; seen.add(c.native_content)
        elif c.classification=='INVALID': counts['invalid']+=1; counts['would_skip']+=1
        else: counts['unsupported']+=1; counts['would_skip']+=1
        out.append(c)
    return DryRunResult(len(rows),candidates=tuple(out),**counts)

def read_synthetic_source_read_only(path: str | Path) -> tuple[LegacyMemoryRecord, ...]:
    uri=f"file:{Path(path).resolve().as_posix()}?mode=ro"
    conn=sqlite3.connect(uri,uri=True); conn.row_factory=sqlite3.Row
    try:
        rows=conn.execute("SELECT id,content,type,importance,confidence,source,created_at,updated_at,status,is_sensitive FROM memories ORDER BY id").fetchall()
        return tuple(LegacyMemoryRecord(r['id'],r['content'],r['type'],r['importance'],r['confidence'],r['source'],r['created_at'],r['updated_at'],r['status'],bool(r['is_sensitive']),"user","default") for r in rows)
    finally: conn.close()

__all__=['MIGRATION_VERSION','LegacyMemoryRecord','MigrationCandidate','DryRunResult','fingerprint','plan','read_synthetic_source_read_only']
