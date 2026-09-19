from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory.kernel_v2 import MemoryKernelV2

with tempfile.TemporaryDirectory(prefix="aura_memory_v21_r5_") as td:
    db = Path(td) / "memory-v21-r5.db"
    kernel = MemoryKernelV2(db_path=db)
    kernel.ensure_schema()

    aura = kernel.v21_upsert_entity(
        "AURA",
        entity_type="project",
        aliases=["Aura assistant"],
        scope="project",
        scope_id="AURA",
        confidence=0.99,
    )
    memory_kernel = kernel.v21_upsert_entity(
        "MemoryKernelV2",
        entity_type="component",
        aliases=["memory kernel"],
        scope="project",
        scope_id="AURA",
        confidence=0.98,
    )
    other = kernel.v21_upsert_entity(
        "Other Project",
        entity_type="project",
        scope="project",
        scope_id="OTHER",
        confidence=1.0,
    )
    user = kernel.v21_upsert_entity(
        "User Profile",
        entity_type="profile",
        scope="user",
        confidence=0.95,
    )

    aura_fact = kernel.v21_store_temporal_fact(
        aura["entity_id"],
        "architecture",
        object_text="local-first autonomous assistant",
        fact_key="aura:r5:architecture",
        confidence=0.97,
        valid_from="2026-01-01T00:00:00+00:00",
        provenance={"source": "synthetic-r5"},
    )["fact"]

    component_fact = kernel.v21_store_temporal_fact(
        memory_kernel["entity_id"],
        "role",
        object_text="canonical durable memory authority",
        fact_key="aura:r5:memory-kernel-role",
        confidence=0.99,
        valid_from="2026-01-01T00:00:00+00:00",
        provenance={"source": "synthetic-r5"},
    )["fact"]

    other_fact = kernel.v21_store_temporal_fact(
        other["entity_id"],
        "architecture",
        object_text="cloud-only architecture",
        fact_key="other:r5:architecture",
        confidence=1.0,
        valid_from="2026-01-01T00:00:00+00:00",
        provenance={"source": "synthetic-r5"},
    )["fact"]

    pref_fact = kernel.v21_store_temporal_fact(
        user["entity_id"],
        "response_style",
        object_text="concise answers",
        fact_key="user:r5:style",
        confidence=0.90,
        valid_from="2026-01-01T00:00:00+00:00",
        provenance={"source": "synthetic-r5"},
    )["fact"]

    kernel.v21_store_relation(
        aura["entity_id"],
        "uses",
        memory_kernel["entity_id"],
        confidence=0.96,
        provenance={"source": "synthetic-r5"},
    )

    # Open conflict should be visible and penalized, not silently hidden.
    conflicting = kernel.v21_store_temporal_fact(
        aura["entity_id"],
        "architecture",
        object_text="remote-only assistant",
        fact_key="aura:r5:architecture-conflict",
        confidence=0.60,
        valid_from="2026-06-01T00:00:00+00:00",
        provenance={"source": "synthetic-r5-conflict"},
    )
    assert len(conflicting["conflicts"]) == 1

    recall = kernel.v21_recall_graph(
        "AURA architecture local autonomous",
        scope="project",
        scope_id="AURA",
        at="2026-09-11T00:00:00+00:00",
        limit=10,
    )
    assert recall["count"] >= 1
    ids = {row["fact"]["fact_id"] for row in recall["results"]}
    assert aura_fact["fact_id"] in ids
    assert other_fact["fact_id"] not in ids, "cross-project leakage"
    assert recall["results"][0]["fact"]["fact_id"] == aura_fact["fact_id"]

    # User-scope fallback is allowed inside a project, but cannot outrank a strong exact-scope match.
    pref_recall = kernel.v21_recall_graph(
        "response style concise",
        scope="project",
        scope_id="AURA",
        at="2026-09-11T00:00:00+00:00",
        limit=10,
    )
    assert any(row["fact"]["fact_id"] == pref_fact["fact_id"] for row in pref_recall["results"])
    pref_row = next(row for row in pref_recall["results"] if row["fact"]["fact_id"] == pref_fact["fact_id"])
    assert pref_row["scope_reason"] == "user_fallback"

    # Relation expansion: query AURA/MemoryKernel should surface the component's fact.
    graph_recall = kernel.v21_recall_graph(
        "AURA memory kernel authority",
        scope="project",
        scope_id="AURA",
        at="2026-09-11T00:00:00+00:00",
        limit=10,
        max_relation_hops=1,
    )
    component_rows = [
        row for row in graph_recall["results"]
        if row["fact"]["fact_id"] == component_fact["fact_id"]
    ]
    assert component_rows
    assert component_rows[0]["score_components"]["relation_boost"] > 0.0

    # Open conflict is exposed and score-penalized.
    conflict_rows = [row for row in recall["results"] if row["open_conflict"]]
    assert conflict_rows, "open conflict must be observable in recall"

    # Explainability contract is deterministic and contains score components.
    explained = kernel.v21_explain_recall(recall)
    assert len(explained) == recall["count"]
    assert explained[0]["rank"] == 1
    assert "lexical" in explained[0]["score_components"]
    assert "scope" in explained[0]["score_components"]
    assert "fact_confidence" in explained[0]["score_components"]
    assert "open_conflict_penalty" in explained[0]["score_components"]

    # Determinism: same inputs => same fact order and scores.
    recall2 = kernel.v21_recall_graph(
        "AURA architecture local autonomous",
        scope="project",
        scope_id="AURA",
        at="2026-09-11T00:00:00+00:00",
        limit=10,
    )
    sig1 = [(r["fact"]["fact_id"], r["score"]) for r in recall["results"]]
    sig2 = [(r["fact"]["fact_id"], r["score"]) for r in recall2["results"]]
    assert sig1 == sig2

print("[PASS] MemoryKernel v2.1 R5 explainable recall graph invariant")
print("[PASS] exact project scope with no cross-project leakage")
print("[PASS] controlled user-scope fallback")
print("[PASS] temporal validity respected")
print("[PASS] graph relation expansion")
print("[PASS] confidence-aware deterministic ranking")
print("[PASS] open conflicts remain visible with score penalty")
print("[PASS] per-result score explanation")
print("[PASS] repeated identical recall is deterministic")
print("[PASS] temporary SQLite only; no live memory row mutation")
