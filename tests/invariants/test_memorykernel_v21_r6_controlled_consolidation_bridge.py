from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory.kernel_v2 import MemoryKernelV2
from runtime.aura_memory_v21_controlled_consolidation_bridge import (
    ConsolidationBlocked,
    ConsolidationMapping,
    ControlledMemoryConsolidationBridge,
)


class FakeStore:
    def __init__(self, candidates):
        self.rows = {x["candidate_id"]: dict(x) for x in candidates}
        self.fail_commit = False
        self.commit_calls = 0

    def list_candidates(self):
        return {"items": [dict(x) for x in self.rows.values()]}

    def consolidation_plan(self):
        return {
            "items": [
                dict(x) for x in self.rows.values()
                if x.get("state") == "approved" and not x.get("consolidated")
            ]
        }

    def consolidate_candidate(self, candidate_id=None, *, user_confirmed=False):
        self.commit_calls += 1
        if not user_confirmed:
            raise PermissionError("confirmation required")
        if self.fail_commit:
            raise RuntimeError("synthetic L170 commit failure")
        row = self.rows[str(candidate_id)]
        if row.get("state") not in {"approved", "consolidated"}:
            raise ValueError("not approved")
        row["state"] = "consolidated"
        row["consolidated"] = True
        return {"candidate": dict(row), "controlled_learning_ledger_write_performed": True}


def candidate(cid, fp, *, approved=True, state="approved", consolidated=False, conflict_with=None):
    return {
        "candidate_id": cid,
        "fingerprint": fp,
        "state": state,
        "requires_explicit_approval": True,
        "approved": approved,
        "consolidated": consolidated,
        "duplicate_of": None,
        "conflict_with": conflict_with,
        "source": {
            "source_kind": "conversation",
            "source_id": "synthetic-turn",
            "observed_at": "2026-09-11T12:00:00+00:00",
            "extractor": "synthetic-r6",
            "confidence": 0.94,
        },
    }


with tempfile.TemporaryDirectory(prefix="aura_memory_v21_r6_") as td:
    db = Path(td) / "memory-v21-r6.db"
    kernel = MemoryKernelV2(db_path=db)
    kernel.ensure_schema()

    c1 = candidate("c1", "fp-c1")
    c2 = candidate("c2", "fp-c2", approved=False, state="candidate")
    c3 = candidate("c3", "fp-c3")
    c4 = candidate("c4", "fp-c4")
    store = FakeStore([c1, c2, c3, c4])
    bridge = ControlledMemoryConsolidationBridge(kernel, store)

    mapping = ConsolidationMapping(
        subject_name="AURA",
        entity_type="project",
        scope="project",
        scope_id="AURA",
        predicate="architecture",
        object_text="local-first autonomous assistant",
        memory_type="semantic",
        valid_from="2026-01-01T00:00:00+00:00",
    )

    # No approval bypass.
    try:
        bridge.consolidate("c1", mapping, explicit_confirmation=False)
        raise AssertionError("missing explicit confirmation was accepted")
    except ConsolidationBlocked:
        pass

    try:
        bridge.consolidate(
            "c2",
            mapping,
            explicit_confirmation=True,
        )
        raise AssertionError("unapproved candidate was consolidated")
    except ConsolidationBlocked:
        pass

    # Approved candidate -> canonical graph + L170 commit.
    result = bridge.consolidate("c1", mapping, explicit_confirmation=True)
    assert result["status"] == "consolidated"
    assert result["canonical_committed"] is True
    assert result["l170_committed"] is True
    assert store.rows["c1"]["state"] == "consolidated"

    memory_id = result["memory_id"]
    fact_id = result["fact_id"]

    con = kernel._connect()
    try:
        m = con.execute(
            "SELECT provenance_json FROM memory_kernel_v2_records WHERE memory_id=?",
            (memory_id,),
        ).fetchone()
        f = con.execute(
            "SELECT provenance_json FROM memory_v21_facts WHERE fact_id=?",
            (fact_id,),
        ).fetchone()
        assert m is not None and f is not None
        assert "l170_candidate_id" in m["provenance_json"]
        assert "explicit_approval_verified" in f["provenance_json"]
    finally:
        con.close()

    # Re-run after completed commit -> exactly idempotent, no duplicate write.
    before_calls = store.commit_calls
    again = bridge.consolidate("c1", mapping, explicit_confirmation=True)
    assert again["status"] == "already_consolidated"
    assert again["idempotent"] is True
    assert store.commit_calls == before_calls

    # Existing contradictory fact blocks BEFORE canonical/L170 mutation.
    conflicting_mapping = ConsolidationMapping(
        subject_name="AURA",
        entity_type="project",
        scope="project",
        scope_id="AURA",
        predicate="architecture",
        object_text="remote-only assistant",
        memory_type="semantic",
        valid_from="2026-06-01T00:00:00+00:00",
    )
    preview = bridge.preview(store.rows["c3"], conflicting_mapping)
    assert preview["blocked"] is True
    assert preview["predicted_conflicts"]

    try:
        bridge.consolidate("c3", conflicting_mapping, explicit_confirmation=True)
        raise AssertionError("predicted conflict was not blocked")
    except ConsolidationBlocked:
        pass
    assert store.rows["c3"]["state"] == "approved"

    # If L170 commit fails after canonical staging, the bridge rolls its own
    # newly-created canonical rows back.
    safe_mapping = ConsolidationMapping(
        subject_name="AURA",
        entity_type="project",
        scope="project",
        scope_id="AURA",
        predicate="release_channel",
        object_text="stable",
        memory_type="semantic",
        valid_from="2026-01-01T00:00:00+00:00",
    )
    p4 = bridge.preview(store.rows["c4"], safe_mapping)
    store.fail_commit = True
    try:
        bridge.consolidate("c4", safe_mapping, explicit_confirmation=True)
        raise AssertionError("synthetic L170 failure did not propagate")
    except RuntimeError as exc:
        assert "synthetic L170 commit failure" in str(exc)
    finally:
        store.fail_commit = False

    assert not bridge._memory_exists(p4["memory_id"])
    assert bridge._fact_by_key(p4["fact_key"]) is None
    assert store.rows["c4"]["state"] == "approved"

print("[PASS] MemoryKernel v2.1 R6 controlled consolidation bridge invariant")
print("[PASS] explicit confirmation cannot be bypassed")
print("[PASS] unapproved learning candidate cannot reach canonical memory")
print("[PASS] approved candidate -> canonical memory + graph fact + L170 ledger")
print("[PASS] candidate fingerprint creates deterministic canonical identity")
print("[PASS] full L170 provenance preserved in canonical memory")
print("[PASS] completed consolidation is idempotent")
print("[PASS] predicted graph contradiction blocks before mutation")
print("[PASS] L170 commit failure rolls back new canonical writes")
print("[PASS] temporary SQLite + synthetic L170 store only")
