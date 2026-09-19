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
    ConversationMemoryIntegration,
)
from core.router import ActionRouter
from core.aura_core import AuraCore


class _Decision:
    allowed = True
    confirmation_required = False


class _Security:
    def authorize(self, *args, **kwargs):
        return _Decision()


tmp = tempfile.TemporaryDirectory(prefix="aura_v211_r6_")
db = None
try:
    db_path = Path(tmp.name) / "aura.db"
    db = Database(db_path)
    manager = MemoryManager(db)

    core = object.__new__(AuraCore)
    core.memory_manager = manager
    adapter = core.conversation_memory_v211()

    # ------------------------------------------------------------
    # 1) Stale legacy 1.0 + canonical 1.0 -> 1.1 correction.
    # ------------------------------------------------------------
    manager.remember(
        "La version de TEST-R6 est 1.0",
        memory_type="fact",
        source="explicit_user",
        importance=4,
    )

    new = adapter.plan_message(
        "Retiens que la version de TEST-R6 est 1.0.",
        observed_at="2026-09-11T14:00:00+00:00",
    )
    adapter.commit_explicit_fact(new)

    update = adapter.plan_message(
        "Correction : la version actuelle de TEST-R6 est 1.1.",
        observed_at="2026-09-11T14:01:00+00:00",
    )
    updated = adapter.commit_explicit_fact(update)
    assert updated["fact"]["object_text"] == "1.1"

    answer_result = adapter.answer_personal_query(
        "Quelle est la version actuelle de TEST-R6 ?",
        scope="user",
    )
    assert answer_result["status"] == "answered"
    assert answer_result["canonical"] is True
    assert "1.1" in answer_result["answer"]
    assert "1.0" not in answer_result["answer"]
    assert answer_result["conflict"] is False

    explanation = adapter.explain_last_answer()
    assert explanation
    assert "MemoryKernelV2" in explanation
    assert "1.1" in explanation

    assert adapter.can_answer_personal_query(
        "Quelle est la version actuelle de TEST-R6 ?"
    ) is True

    # ------------------------------------------------------------
    # 2) Real open contradiction must state both values.
    # ------------------------------------------------------------
    local = adapter.plan_message(
        "TEST-CONFLICT-R6 fonctionne en mode local.",
        observed_at="2026-09-11T14:02:00+00:00",
    )
    local_result = adapter.commit_explicit_fact(
        local,
        explicit_user_authorization=True,
    )

    cloud = adapter.plan_message(
        "TEST-CONFLICT-R6 fonctionne uniquement dans le cloud.",
        observed_at="2026-09-11T14:03:00+00:00",
    )
    assert cloud.operation == "CONTRADICTION"
    cloud_result = adapter.commit_explicit_fact(
        cloud,
        explicit_user_authorization=True,
    )
    assert cloud_result["conflicts"]

    conflict_answer = adapter.answer_personal_query(
        "Que sais-tu du mode de fonctionnement de TEST-CONFLICT-R6 ?",
        scope="user",
    )
    assert conflict_answer["status"] == "answered"
    assert conflict_answer["conflict"] is True
    folded_answer = conflict_answer["answer"].casefold()
    assert "contradictoires" in folded_answer
    assert "local" in folded_answer
    assert "cloud" in folded_answer
    assert "je ne choisis pas arbitrairement" in folded_answer

    conflict_explanation = adapter.explain_last_answer()
    assert "conflit ouvert" in conflict_explanation.casefold()
    assert "MemoryKernelV2" in conflict_explanation

    # ------------------------------------------------------------
    # 3) Core helper: canonical first; stale legacy cannot override.
    # ------------------------------------------------------------
    core_answer = core.answer_memory_query_v211(
        "Quelle est la version actuelle de TEST-R6 ?"
    )
    assert core_answer is not None
    assert "1.1" in core_answer
    assert "1.0" not in core_answer
    assert core.can_answer_memory_query_v211(
        "Quelle est la version actuelle de TEST-R6 ?"
    ) is True

    # ------------------------------------------------------------
    # 4) Router direct ANSWER_MEMORY_QUERY is canonical-first.
    # ------------------------------------------------------------
    router = ActionRouter(
        None,
        None,
        None,
        _Security(),
        memory_manager=manager,
    )
    router_answer = router._answer_memory_query(
        "Quelle est la version actuelle de TEST-R6 ?"
    )
    assert "1.1" in router_answer
    assert "1.0" not in router_answer

    router._answer_memory_query(
        "Que sais-tu du mode de fonctionnement de TEST-CONFLICT-R6 ?"
    )
    router_explanation = router._explain_memory()
    assert "MemoryKernelV2" in router_explanation
    assert "conflit ouvert" in router_explanation.casefold()

    # ------------------------------------------------------------
    # 5) Legacy fallback only if canonical memory is empty.
    # ------------------------------------------------------------
    manager.remember(
        "je préfère le thé vert",
        memory_type="preference",
        source="explicit_user",
        importance=4,
    )
    legacy_query = "Quelle est ma préférence pour le thé ?"
    legacy_direct = manager.answer_personal_question(legacy_query)

    # The graph may still return unrelated canonical candidates. The direct
    # answer layer must reject them as insufficiently relevant.
    irrelevant_probe = adapter.answer_personal_query(
        legacy_query,
        scope="user",
    )
    assert irrelevant_probe["status"] == "empty"
    assert irrelevant_probe.get("reason") == "no_relevant_canonical_results"

    fallback = core.answer_memory_query_v211(legacy_query)

    # Once the canonical direct-answer relevance gate says "empty", the
    # compatibility result must be exactly the preserved legacy answer.
    assert fallback == legacy_direct
    assert fallback is not None

    # ------------------------------------------------------------
    # 6) Private mode fail-closed.
    # ------------------------------------------------------------
    manager.set_private_mode(True)
    assert core.answer_memory_query_v211(
        "Quelle est la version actuelle de TEST-R6 ?"
    ) is None
    assert core.can_answer_memory_query_v211(
        "Quelle est la version actuelle de TEST-R6 ?"
    ) is False
    manager.set_private_mode(False)

    # ------------------------------------------------------------
    # 7) Static binding checks for live source.
    # ------------------------------------------------------------
    core_source = (ROOT / "core" / "aura_core.py").read_text(
        encoding="utf-8", errors="ignore"
    )
    main_source = (ROOT / "ui" / "main_window.py").read_text(
        encoding="utf-8", errors="ignore"
    )
    router_source = (ROOT / "core" / "router.py").read_text(
        encoding="utf-8", errors="ignore"
    )

    assert "self.can_answer_memory_query_v211(text)" in core_source
    assert "fallback = self.aura_core.answer_memory_query_v211(text)" in main_source
    assert (
        "fallback = self.aura_core.memory_manager.answer_personal_question(text)"
        not in main_source
    )
    assert "_aura_v211_r6_answer_memory_query" in router_source
    assert "_aura_v211_r6_explain_memory" in router_source

finally:
    if db is not None:
        try:
            if hasattr(db, "close"):
                db.close()
            else:
                db.conn.close()
        except Exception:
            pass
    tmp.cleanup()

print("[PASS] AURA v2.1.1 R6 canonical answers + explainability invariant")
print("[PASS] canonical corrected 1.1 answers directly and stale legacy 1.0 is excluded")
print("[PASS] open local/cloud contradiction answers with both values and no invented certainty")
print("[PASS] provenance/conflict explanation names MemoryKernelV2")
print("[PASS] AuraCore canonical answer detection is active")
print("[PASS] ActionRouter ANSWER_MEMORY_QUERY is canonical-first")
print("[PASS] ActionRouter memory explanation uses canonical last-answer evidence")
print("[PASS] irrelevant canonical candidates are rejected before legacy fallback")
print("[PASS] relevance-empty fallback is byte-for-byte equivalent to direct legacy personal answer")
print("[PASS] main_window direct legacy personal fallback is removed")
print("[PASS] private mode remains fail-closed")
print("[PASS] temporary SQLite only; no live memory row mutation")
