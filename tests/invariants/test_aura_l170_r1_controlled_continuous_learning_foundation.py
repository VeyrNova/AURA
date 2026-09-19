from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_controlled_continuous_learning_v170 import (
    ControlledContinuousLearningEngine,
    capability_snapshot,
)

ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


road_sha = sha(ROADMAP)

caps = capability_snapshot()
assert caps["candidate_proposal"] is True
assert caps["provenance_required"] is True
assert caps["duplicate_detection"] is True
assert caps["conflict_detection"] is True
assert caps["explicit_approval_required"] is True
assert caps["live_memory_mutation"] is False
assert caps["model_weight_mutation"] is False
assert caps["autonomous_self_modification"] is False

engine = ControlledContinuousLearningEngine()

prov = {
    "source_kind": "conversation",
    "source_ref": "turn-test-1",
    "observed_at": "2026-09-05T15:00:00+02:00",
    "extractor": "test",
    "confidence": 0.95,
}

a = engine.propose_candidate(
    subject="Neural Echo",
    predicate="release cadence",
    value="one song every Friday",
    provenance=prov,
    importance=0.8,
)
assert a["state"] == "candidate"
assert a["requires_explicit_approval"] is True
assert a["approved"] is False

dup = engine.propose_candidate(
    subject="Neural Echo",
    predicate="release cadence",
    value="one song every Friday",
    provenance={**prov, "source_ref": "turn-test-2"},
)
assert dup["state"] == "duplicate"
assert dup["duplicate_of"] == a["candidate_id"]

conflict = engine.propose_candidate(
    subject="Neural Echo",
    predicate="release cadence",
    value="one song every Sunday",
    provenance={**prov, "source_ref": "turn-test-3"},
)
assert conflict["state"] == "conflict_review"
assert a["candidate_id"] in conflict["conflict_with"]

try:
    engine.approve_candidate(a["candidate_id"], user_confirmed=False)
    raise AssertionError("approval without confirmation must fail")
except PermissionError:
    pass

approved = engine.approve_candidate(
    a["candidate_id"],
    user_confirmed=True,
)
assert approved["state"] == "approved"
assert approved["approved"] is True

try:
    engine.approve_candidate(conflict["candidate_id"], user_confirmed=True)
    raise AssertionError("unresolved conflict must not be approved")
except ValueError:
    pass

resolved = engine.resolve_conflict(
    conflict["candidate_id"],
    keep_candidate=False,
    user_confirmed=True,
)
assert resolved["state"] == "rejected"

plan = engine.consolidation_plan()
assert plan["count"] == 1
assert plan["items"][0]["candidate_id"] == a["candidate_id"]
assert plan["live_memory_mutation_performed"] is False
assert plan["model_weight_mutation_performed"] is False

commit = engine.mark_consolidated(
    [a["candidate_id"]],
    user_confirmed=True,
)
assert commit["candidate_ids"] == [a["candidate_id"]]
assert commit["live_memory_mutation_performed"] is False
assert commit["model_weight_mutation_performed"] is False

audit = engine.audit_log()
assert [x["event"] for x in audit] == [
    "candidate_proposed",
    "candidate_proposed",
    "candidate_proposed",
    "candidate_approved",
    "conflict_resolved",
    "candidate_consolidated",
]

assert sha(ROADMAP) == road_sha

print("[PASS] provenance-aware learning candidate")
print("[PASS] duplicate detection")
print("[PASS] conflict detection + explicit conflict resolution")
print("[PASS] explicit approval required")
print("[PASS] controlled consolidation plan")
print("[PASS] immutable-style audit event sequence")
print("[PASS] no live-memory mutation in R1")
print("[PASS] no model-weight mutation")
print("[PASS] no autonomous self-modification")
print("[PASS] live Roadmap unchanged")
