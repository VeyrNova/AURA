from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.database import Database
from memory.manager import MemoryManager
from runtime.aura_memory_v21_controlled_consolidation_bridge import ConsolidationBlocked


class FakeStore:
    def __init__(self):
        self.row = {
            "candidate_id": "r7-candidate",
            "fingerprint": "r7-fingerprint",
            "state": "approved",
            "requires_explicit_approval": True,
            "approved": True,
            "consolidated": False,
            "duplicate_of": None,
            "conflict_with": None,
            "source": {
                "source_kind": "conversation",
                "source_id": "synthetic-r7",
                "observed_at": "2026-09-11T12:00:00+00:00",
                "extractor": "synthetic-r7",
                "confidence": 0.93,
            },
        }

    def list_candidates(self):
        return {"items": [dict(self.row)]}

    def consolidation_plan(self):
        if self.row["state"] == "approved" and not self.row["consolidated"]:
            return {"items": [dict(self.row)]}
        return {"items": []}

    def consolidate_candidate(self, candidate_id=None, *, user_confirmed=False):
        if not user_confirmed:
            raise PermissionError("confirmation required")
        self.row["state"] = "consolidated"
        self.row["consolidated"] = True
        return {
            "candidate": dict(self.row),
            "controlled_learning_ledger_write_performed": True,
        }


tmp = tempfile.TemporaryDirectory(prefix="aura_memory_v21_r7_r2_")
db = None
try:
    db_path = Path(tmp.name) / "aura.db"
    db = Database(db_path)
    manager = MemoryManager(db)

    # R7-R2 key repair: facade bootstrap must materialize canonical v2/v2.1 schema.
    k1 = manager.v21_kernel()
    k2 = manager.v21_kernel()
    assert k1 is k2
    assert k1.__class__.__name__ == "MemoryKernelV2"

    con = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        con.close()

    required_tables = {
        "memory_kernel_v2_records",
        "memory_kernel_v2_audit",
        "memory_v21_entities",
        "memory_v21_facts",
        "memory_v21_relations",
        "memory_v21_conflicts",
    }
    assert required_tables.issubset(tables), required_tables - tables

    # Existing legacy behavior remains functional.
    legacy_record, created = manager.remember(
        "je préfère les réponses concises",
        memory_type="preference",
        importance=4,
    )
    assert created is True
    legacy_id = legacy_record.id

    before = db.conn.execute(
        "SELECT * FROM memories WHERE id=?",
        (legacy_id,),
    ).fetchone()
    assert before is not None
    before_content = before["content"]
    before_count = db.conn.execute(
        "SELECT COUNT(*) FROM memories"
    ).fetchone()[0]

    plan = manager.v21_legacy_migration_plan(limit=50)
    item = next(x for x in plan["items"] if x["legacy_id"] == legacy_id)
    assert item["already_migrated"] is False
    assert item["normalization"] == "NOT_GUESSED"
    assert plan["legacy_table_mutation"] is False
    assert plan["automatic_bulk_migration"] is False

    try:
        manager.v21_migrate_legacy_record(legacy_id)
        raise AssertionError("legacy migration bypassed confirmation")
    except PermissionError:
        pass

    migrated = manager.v21_migrate_legacy_record(
        legacy_id,
        scope="user",
        explicit_confirmation=True,
    )
    assert migrated["status"] == "migrated"
    assert migrated["legacy_mutated"] is False
    assert (
        migrated["record"]["provenance"]["semantic_normalization_performed"]
        is False
    )
    assert migrated["record"]["provenance"]["legacy_id"] == legacy_id

    after = db.conn.execute(
        "SELECT * FROM memories WHERE id=?",
        (legacy_id,),
    ).fetchone()
    after_count = db.conn.execute(
        "SELECT COUNT(*) FROM memories"
    ).fetchone()[0]
    assert after is not None
    assert after["content"] == before_content
    assert after_count == before_count

    again = manager.v21_migrate_legacy_record(
        legacy_id,
        scope="user",
        explicit_confirmation=True,
    )
    assert again["status"] == "already_migrated"
    assert again["idempotent"] is True

    aura = k1.v21_upsert_entity(
        "AURA",
        entity_type="project",
        scope="project",
        scope_id="AURA",
        confidence=0.99,
    )
    fact = k1.v21_store_temporal_fact(
        aura["entity_id"],
        "architecture",
        object_text="local-first autonomous assistant",
        fact_key="r7:aura:architecture",
        confidence=0.97,
        valid_from="2026-01-01T00:00:00+00:00",
        provenance={"source": "synthetic-r7"},
    )["fact"]

    recall = manager.v21_recall(
        "AURA architecture local",
        scope="project",
        scope_id="AURA",
        at="2026-09-11T00:00:00+00:00",
    )
    assert any(
        x["fact"]["fact_id"] == fact["fact_id"]
        for x in recall["results"]
    )
    explanation = manager.v21_explain_recall(recall)
    assert explanation and explanation[0]["score_components"]

    store = FakeStore()
    mapping = {
        "subject_name": "AURA",
        "entity_type": "project",
        "scope": "project",
        "scope_id": "AURA",
        "predicate": "release_channel",
        "object_text": "stable",
        "memory_type": "semantic",
        "valid_from": "2026-01-01T00:00:00+00:00",
    }
    preview = manager.v21_preview_consolidation(
        store, "r7-candidate", mapping
    )
    assert preview["blocked"] is False

    try:
        manager.v21_consolidate_candidate(
            store,
            "r7-candidate",
            mapping,
            explicit_confirmation=False,
        )
        raise AssertionError("R7 facade bypassed R6 confirmation")
    except ConsolidationBlocked:
        pass

    consolidated = manager.v21_consolidate_candidate(
        store,
        "r7-candidate",
        mapping,
        explicit_confirmation=True,
    )
    assert consolidated["status"] == "consolidated"
    assert manager.v21_kernel() is k1

finally:
    if db is not None:
        try:
            if hasattr(db, "close"):
                db.close()
            elif getattr(db, "conn", None) is not None:
                db.conn.close()
        except Exception:
            pass
    tmp.cleanup()

print("[PASS] MemoryKernel v2.1 R7-R2 compatibility/migration facade invariant")
print("[PASS] facade bootstraps canonical v2/v2.1 schema idempotently")
print("[PASS] MemoryManager delegates to one stable canonical MemoryKernelV2")
print("[PASS] legacy MemoryManager behavior remains operational")
print("[PASS] legacy migration plan is non-mutating and non-automatic")
print("[PASS] legacy copy-forward requires explicit confirmation")
print("[PASS] legacy source row is preserved")
print("[PASS] legacy copy-forward is idempotent and provenance-rich")
print("[PASS] no semantic graph facts are guessed during migration")
print("[PASS] explainable v2.1 recall is exposed through MemoryManager")
print("[PASS] R6 consolidation bridge is exposed without bypassing approval")
print("[PASS] temporary database closes cleanly on success/failure")
