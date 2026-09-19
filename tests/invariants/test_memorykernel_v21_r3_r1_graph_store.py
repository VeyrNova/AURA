from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory.kernel_v2 import MemoryKernelV2

with tempfile.TemporaryDirectory(prefix="aura_memory_v21_r3_r1_") as td:
    db = Path(td) / "memory-v21-r3-r1.db"
    kernel = MemoryKernelV2(db_path=db)
    kernel.ensure_schema()

    con = sqlite3.connect(db)
    try:
        tables = {
            row[0]
            for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        con.close()

    expected = {
        "memory_kernel_v2_records",
        "memory_kernel_v2_audit",
        "memory_v21_entities",
        "memory_v21_facts",
        "memory_v21_relations",
        "memory_v21_conflicts",
    }
    assert expected.issubset(tables), expected - tables

    aura = kernel.v21_upsert_entity(
        "AURA",
        entity_type="project",
        aliases=["AURA project"],
        scope="project",
        scope_id="AURA",
        confidence=0.98,
    )
    aura2 = kernel.v21_upsert_entity(
        "AURA",
        entity_type="project",
        aliases=["Project AURA"],
        scope="project",
        scope_id="AURA",
        confidence=0.99,
    )
    assert aura["entity_id"] == aura2["entity_id"]
    assert set(aura2["aliases"]) == {"AURA project", "Project AURA"}
    assert abs(aura2["confidence"] - 0.99) < 1e-9

    fact1 = kernel.v21_store_fact(
        aura["entity_id"],
        "architecture",
        object_text="local-first",
        fact_key="project:aura:architecture",
        confidence=0.95,
        observed_at="2026-09-11T14:00:00+00:00",
        valid_from="2026-09-11T00:00:00+00:00",
        provenance={"source": "synthetic-r3-r1"},
    )
    fact2 = kernel.v21_store_fact(
        aura["entity_id"],
        "architecture",
        object_text="local-first",
        fact_key="project:aura:architecture",
        confidence=0.97,
        observed_at="2026-09-11T14:01:00+00:00",
        valid_from="2026-09-11T00:00:00+00:00",
        provenance={"source": "synthetic-r3-r1-update"},
    )
    assert fact1["fact_id"] == fact2["fact_id"]
    assert fact2["version"] == 2
    assert abs(fact2["confidence"] - 0.97) < 1e-9

    neural = kernel.v21_upsert_entity(
        "Neural Echo",
        entity_type="project",
        scope="user",
        confidence=0.90,
    )

    rel1 = kernel.v21_store_relation(
        aura["entity_id"],
        "coexists_with",
        neural["entity_id"],
        confidence=0.88,
        provenance={"source": "synthetic-r3-r1"},
    )
    rel2 = kernel.v21_store_relation(
        aura["entity_id"],
        "coexists_with",
        neural["entity_id"],
        confidence=0.90,
        provenance={"source": "synthetic-r3-r1-update"},
    )
    assert rel1["relation_id"] == rel2["relation_id"]
    assert rel2["version"] == 2

    facts = kernel.v21_list_facts(
        subject_entity_id=aura["entity_id"],
        predicate="architecture",
    )
    relations = kernel.v21_list_relations(
        subject_entity_id=aura["entity_id"],
        predicate="coexists_with",
    )
    assert len(facts) == 1
    assert len(relations) == 1

    con = sqlite3.connect(db)
    try:
        audit_actions = [
            row[0]
            for row in con.execute(
                "SELECT action FROM memory_kernel_v2_audit ORDER BY audit_id"
            ).fetchall()
        ]
    finally:
        con.close()

    for required in (
        "v21.entity.remember",
        "v21.entity.upsert",
        "v21.fact.remember",
        "v21.fact.update",
        "v21.relation.remember",
        "v21.relation.update",
    ):
        assert required in audit_actions, (required, audit_actions)

print("[PASS] MemoryKernel v2.1 R3-R1 graph store invariant")
print("[PASS] AURA root bootstrap")
print("[PASS] four v2.1 tables on temporary SQLite")
print("[PASS] entity dedupe + alias merge")
print("[PASS] fact stable-key versioning")
print("[PASS] relation tuple versioning")
print("[PASS] canonical audit trail")
print("[PASS] no live memory row mutation")
