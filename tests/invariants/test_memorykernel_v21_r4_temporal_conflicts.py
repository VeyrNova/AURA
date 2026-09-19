from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory.kernel_v2 import MemoryKernelV2

with tempfile.TemporaryDirectory(prefix="aura_memory_v21_r4_") as td:
    db = Path(td) / "memory-v21-r4.db"
    kernel = MemoryKernelV2(db_path=db)
    kernel.ensure_schema()

    subject = kernel.v21_upsert_entity(
        "AURA",
        entity_type="project",
        scope="project",
        scope_id="AURA",
        confidence=0.99,
    )

    # Temporal validation.
    valid = kernel.v21_validate_temporal(
        observed_at="2026-09-11T12:00:00+00:00",
        valid_from="2026-01-01T00:00:00+00:00",
        valid_to="2026-12-31T23:59:59+00:00",
    )
    assert valid["valid_from"].startswith("2026-01-01T00:00:00")

    try:
        kernel.v21_validate_temporal(
            valid_from="2026-12-31T00:00:00+00:00",
            valid_to="2026-01-01T00:00:00+00:00",
        )
        raise AssertionError("invalid interval was accepted")
    except ValueError:
        pass

    assert kernel.v21_temporal_overlap(
        "2026-01-01T00:00:00+00:00", "2026-12-31T00:00:00+00:00",
        "2026-06-01T00:00:00+00:00", None,
    ) is True
    assert kernel.v21_temporal_overlap(
        "2024-01-01T00:00:00+00:00", "2024-12-31T00:00:00+00:00",
        "2026-01-01T00:00:00+00:00", None,
    ) is False

    first = kernel.v21_store_temporal_fact(
        subject["entity_id"],
        "architecture",
        object_text="local-first",
        fact_key="aura:architecture:local-first",
        confidence=0.96,
        observed_at="2026-01-10T00:00:00+00:00",
        valid_from="2026-01-01T00:00:00+00:00",
        provenance={"source": "synthetic-r4-left"},
    )
    assert first["conflicts"] == []

    second = kernel.v21_store_temporal_fact(
        subject["entity_id"],
        "architecture",
        object_text="cloud-first",
        fact_key="aura:architecture:cloud-first",
        confidence=0.80,
        observed_at="2026-06-10T00:00:00+00:00",
        valid_from="2026-06-01T00:00:00+00:00",
        provenance={"source": "synthetic-r4-right"},
    )
    assert len(second["conflicts"]) == 1
    conflict = second["conflicts"][0]
    assert conflict["state"] == "open"

    # Idempotent reopen.
    same = kernel.v21_open_conflict(
        conflict["right_fact_id"],
        conflict["left_fact_id"],
        reason="duplicate-test",
    )
    assert same["conflict_id"] == conflict["conflict_id"]

    # Non-overlapping contradictory historical fact should not create another conflict.
    historical = kernel.v21_store_temporal_fact(
        subject["entity_id"],
        "architecture",
        object_text="prototype-only",
        fact_key="aura:architecture:prototype",
        confidence=0.70,
        observed_at="2024-06-01T00:00:00+00:00",
        valid_from="2024-01-01T00:00:00+00:00",
        valid_to="2024-12-31T23:59:59+00:00",
        provenance={"source": "synthetic-r4-history"},
    )
    assert historical["conflicts"] == []

    active_july = kernel.v21_list_facts_at(
        subject_entity_id=subject["entity_id"],
        predicate="architecture",
        at="2026-07-01T00:00:00+00:00",
    )
    assert {x["object_text"] for x in active_july} == {"local-first", "cloud-first"}

    resolved = kernel.v21_resolve_conflict(
        conflict["conflict_id"],
        resolution="keep_right",
        note="synthetic deterministic resolution",
    )
    assert resolved["state"] == "resolved"
    assert resolved["resolution"]["resolution"] == "keep_right"

    left = kernel.v21_fact_by_id(conflict["left_fact_id"])
    right = kernel.v21_fact_by_id(conflict["right_fact_id"])
    assert left["status"] == "superseded"
    assert right["status"] == "active"

    active_after = kernel.v21_list_facts_at(
        subject_entity_id=subject["entity_id"],
        predicate="architecture",
        at="2026-07-01T00:00:00+00:00",
    )
    assert [x["object_text"] for x in active_after] == ["cloud-first"]

    assert kernel.v21_list_conflicts(state="open") == []
    resolved_rows = kernel.v21_list_conflicts(state="resolved")
    assert len(resolved_rows) == 1

    con = sqlite3.connect(db)
    try:
        actions = [
            row[0]
            for row in con.execute(
                "SELECT action FROM memory_kernel_v2_audit ORDER BY audit_id"
            ).fetchall()
        ]
    finally:
        con.close()

    assert "v21.conflict.open" in actions
    assert "v21.conflict.resolve" in actions

print("[PASS] MemoryKernel v2.1 R4 temporal + conflict invariant")
print("[PASS] interval validation + overlap")
print("[PASS] temporal point-in-time recall")
print("[PASS] contradictory overlapping facts open one idempotent conflict")
print("[PASS] non-overlapping history does not conflict")
print("[PASS] explicit keep_right resolution supersedes loser")
print("[PASS] conflict open/resolve audit trail")
print("[PASS] temporary SQLite only; no live memory row mutation")
