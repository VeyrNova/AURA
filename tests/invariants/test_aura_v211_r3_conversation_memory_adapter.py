from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.database import Database
from memory.manager import MemoryManager
from runtime.aura_conversation_memory_integration_v211 import (
    CanonicalUpdateBindingRequired,
    ConversationMemoryIntegration,
    MemoryAuthorizationRequired,
)


tmp = tempfile.TemporaryDirectory(prefix="aura_v211_r3_")
db = None
try:
    db_path = Path(tmp.name) / "aura.db"
    db = Database(db_path)
    manager = MemoryManager(db)
    adapter = ConversationMemoryIntegration(manager)

    assert adapter.kernel is manager.v21_kernel()
    assert adapter.kernel.__class__.__name__ == "MemoryKernelV2"

    # NEW — explicit "Retiens que".
    d1 = adapter.plan_message(
        "Retiens que la version de TEST-MEMORY est 1.0.",
        observed_at="2026-09-11T12:00:00+00:00",
    )
    assert d1.operation == "NEW", d1
    assert d1.candidate is not None
    assert d1.candidate.subject == "TEST-MEMORY"
    assert d1.candidate.predicate == "version"
    assert d1.candidate.object_text == "1.0"
    assert d1.candidate.explicit_user_authorization is True
    r1 = adapter.commit_explicit_fact(d1)
    assert r1["status"] == "committed"
    assert r1["operation"] == "NEW"

    # UNCHANGED is idempotent.
    d_same = adapter.plan_message(
        "Retiens que la version de TEST-MEMORY est 1.0.",
        observed_at="2026-09-11T12:01:00+00:00",
    )
    assert d_same.operation == "UNCHANGED"
    same_result = adapter.commit_explicit_fact(d_same)
    assert same_result["canonical_write"] is False

    # UPDATE — deterministic correction classification. R3 MUST fail closed
    # instead of appending a contradictory 1.1 or overwriting legacy memory.
    d2 = adapter.plan_message(
        "Correction : la version actuelle de TEST-MEMORY est 1.1.",
        observed_at="2026-09-11T12:02:00+00:00",
    )
    assert d2.operation == "UPDATE", d2
    assert d2.requires_canonical_supersession is True
    assert d2.candidate is not None and d2.candidate.object_text == "1.1"
    try:
        adapter.commit_explicit_fact(d2)
        raise AssertionError("R3 UPDATE silently committed without canonical supersession binding")
    except CanonicalUpdateBindingRequired:
        pass

    # Verify the failed-closed UPDATE did not mutate durable truth.
    entity = adapter._find_entity(d1.candidate)
    version_facts = adapter.kernel.v21_list_facts(
        subject_entity_id=entity["entity_id"],
        predicate="version",
        status="active",
        limit=50,
    )
    assert len(version_facts) == 1
    assert version_facts[0]["object_text"] == "1.0"

    # Authorization boundary: plain declarative facts can be classified but
    # cannot become durable directly in R3.
    plain = adapter.plan_message(
        "TEST-NOAUTH fonctionne en mode local.",
        observed_at="2026-09-11T12:03:00+00:00",
    )
    assert plain.operation == "NEW"
    assert plain.candidate is not None
    assert plain.candidate.explicit_user_authorization is False
    try:
        adapter.commit_explicit_fact(plain)
        raise AssertionError("non-authorized declarative fact reached durable memory")
    except MemoryAuthorizationRequired:
        pass

    # CONTRADICTION — explicit authorization supplied by the caller to model
    # the approved route. Both facts remain and the kernel opens one conflict.
    local_d = adapter.plan_message(
        "TEST-CONFLICT fonctionne en mode local.",
        observed_at="2026-09-11T12:04:00+00:00",
    )
    assert local_d.operation == "NEW"
    local_r = adapter.commit_explicit_fact(
        local_d,
        explicit_user_authorization=True,
    )
    assert local_r["operation"] == "NEW"

    cloud_d = adapter.plan_message(
        "TEST-CONFLICT fonctionne uniquement dans le cloud.",
        observed_at="2026-09-11T12:05:00+00:00",
    )
    assert cloud_d.operation == "CONTRADICTION", cloud_d
    cloud_r = adapter.commit_explicit_fact(
        cloud_d,
        explicit_user_authorization=True,
    )
    assert cloud_r["operation"] == "CONTRADICTION"
    assert len(cloud_r["conflicts"]) == 1

    conflict_entity = adapter._find_entity(local_d.candidate)
    conflict_facts = adapter.kernel.v21_list_facts(
        subject_entity_id=conflict_entity["entity_id"],
        predicate="operating_mode",
        status="active",
        limit=50,
    )
    assert len(conflict_facts) == 2

    # TEMPORAL_TRANSITION — historical January fact then an open-ended
    # September fact must not be treated as contradiction.
    jan = adapter.plan_message(
        "En janvier 2026, TEST-TEMP utilisait le moteur ALPHA.",
        observed_at="2026-01-15T12:00:00+00:00",
    )
    assert jan.operation == "NEW", jan
    assert jan.candidate is not None
    assert jan.candidate.valid_from.startswith("2026-01-01")
    assert jan.candidate.valid_to.startswith("2026-01-31")
    jan_r = adapter.commit_explicit_fact(
        jan,
        explicit_user_authorization=True,
    )
    assert not jan_r["conflicts"]

    sep = adapter.plan_message(
        "Depuis septembre 2026, TEST-TEMP utilise le moteur BETA.",
        observed_at="2026-09-11T12:00:00+00:00",
    )
    assert sep.operation == "TEMPORAL_TRANSITION", sep
    assert sep.candidate is not None
    assert sep.candidate.valid_from.startswith("2026-09-01")
    assert sep.candidate.valid_to is None
    sep_r = adapter.commit_explicit_fact(
        sep,
        explicit_user_authorization=True,
    )
    assert sep_r["operation"] == "TEMPORAL_TRANSITION"
    assert not sep_r["conflicts"]

    # Canonical recall wrapper is available but is not wired to live runtime yet.
    recall = adapter.recall_for_conversation(
        "TEST-CONFLICT mode local cloud",
        scope="user",
        limit=20,
        include_sensitive=False,
    )
    recalled_ids = {x["fact"]["fact_id"] for x in recall["results"]}
    assert local_r["fact"]["fact_id"] in recalled_ids or cloud_r["fact"]["fact_id"] in recalled_ids
    explanation = adapter.explain_recall(recall)
    assert isinstance(explanation, list)

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

print("[PASS] AURA v2.1.1 R3 ConversationMemoryIntegration invariant")
print("[PASS] NEW explicit fact -> canonical MemoryKernelV2")
print("[PASS] UNCHANGED -> idempotent no-write")
print("[PASS] UPDATE 1.0 -> correction 1.1 classified deterministically")
print("[PASS] UPDATE commit fails closed until canonical supersession binding exists")
print("[PASS] failed-closed UPDATE leaves 1.0 canonical state unchanged")
print("[PASS] non-authorized declarative fact cannot write durable memory directly")
print("[PASS] CONTRADICTION local vs cloud -> both facts + canonical conflict ledger")
print("[PASS] TEMPORAL_TRANSITION January ALPHA -> September BETA without conflict")
print("[PASS] canonical v2.1 recall/explanation wrappers operational")
print("[PASS] temporary SQLite only; no live memories touched")
