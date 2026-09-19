
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.database import Database
from memory.manager import MemoryManager
from core.aura_core import AuraCore
from core.router import ActionRouter


class _Decision:
    allowed = True
    confirmation_required = False


class _Security:
    def authorize(self, *args, **kwargs):
        return _Decision()


tmp = tempfile.TemporaryDirectory(prefix="aura_v211_r7_d2_")
db = None

try:
    db_path = Path(tmp.name) / "aura.db"
    db = Database(db_path)
    manager = MemoryManager(db)

    core = object.__new__(AuraCore)
    core.memory_manager = manager
    adapter = core.conversation_memory_v211()

    subject = "AURA-R7-D2-CANARY"

    first = adapter.plan_message(
        f"Retiens que la version de {subject} est 1.0.",
        observed_at="2026-09-11T16:20:00+00:00",
    )
    assert first.operation == "NEW"
    adapter.commit_explicit_fact(first)

    correction_text = f"Correction : la version actuelle de {subject} est 1.1."
    correction = adapter.plan_message(
        correction_text,
        observed_at="2026-09-11T16:21:00+00:00",
    )
    assert correction.operation == "UPDATE"
    corrected = adapter.commit_explicit_fact(correction)
    assert corrected["fact"]["object_text"] == "1.1"

    assert core.explicit_memory_command_v211(correction_text) is True

    local = adapter.plan_message(
        f"Retiens que {subject} fonctionne en mode local.",
        observed_at="2026-09-11T16:22:00+00:00",
    )
    adapter.commit_explicit_fact(local)

    cloud = adapter.plan_message(
        f"Retiens que {subject} fonctionne uniquement dans le cloud.",
        observed_at="2026-09-11T16:23:00+00:00",
    )
    assert cloud.operation == "CONTRADICTION"
    cloud_result = adapter.commit_explicit_fact(cloud)
    assert cloud_result["conflicts"]

    version_answer = adapter.answer_personal_query(
        f"Quelle est la version actuelle de {subject} ?",
        scope="user",
    )
    assert version_answer["status"] == "answered"
    assert version_answer["predicate"] == "version"
    assert "1.1" in version_answer["answer"]
    assert "1.0" not in version_answer["answer"]

    mode_answer = adapter.answer_personal_query(
        f"Que sais-tu du mode de fonctionnement de {subject} ?",
        scope="user",
    )
    assert mode_answer["status"] == "answered"
    assert mode_answer["predicate"] == "operating_mode"
    assert mode_answer["conflict"] is True
    folded = mode_answer["answer"].casefold()
    assert "local" in folded
    assert "cloud" in folded
    assert "contradictoires" in folded

    # Do not reject the generic word "versions" used by the conflict prose.
    # Validate semantics instead: the selected predicate is operating_mode and
    # the returned values are mode values, not the version facts 1.0/1.1.
    assert "mode de fonctionnement" in folded
    assert not any(
        str(value).strip() in {"1.0", "1.1"}
        for value in (mode_answer.get("values") or [])
    )

    router = ActionRouter(
        None,
        None,
        None,
        _Security(),
        memory_manager=manager,
    )
    router_answer = router._answer_memory_query(
        f"Que sais-tu du mode de fonctionnement de {subject} ?"
    )
    assert "local" in router_answer.casefold()
    assert "cloud" in router_answer.casefold()

    # Separate adapter instance through AuraCore must still see the last
    # canonical answer evidence shared through MemoryManager.
    explanation = core.conversation_memory_v211().explain_last_answer()
    assert explanation is not None
    assert "MemoryKernelV2" in explanation
    assert "conflit ouvert" in explanation.casefold()

    explain_text = "Pourquoi as-tu utilisé cette information ? D'où vient ce souvenir ?"
    assert core.memory_explain_query_v211(explain_text) is True
    assert core.explicit_memory_command_v211(explain_text) is False

    core_source = (ROOT / "core" / "aura_core.py").read_text(
        encoding="utf-8", errors="ignore"
    )
    router_source = (ROOT / "core" / "router.py").read_text(
        encoding="utf-8", errors="ignore"
    )

    explicit_anchor = "if self.explicit_memory_command_v211(text):"
    explain_anchor = "elif self.memory_explain_query_v211(text):"
    answer_anchor = "elif intent is None and ("

    assert explicit_anchor in core_source
    assert explain_anchor in core_source
    assert answer_anchor in core_source
    assert core_source.index(explicit_anchor) < core_source.index(explain_anchor)
    assert core_source.index(explain_anchor) < core_source.index(answer_anchor)

    assert 'intent, params = "CREATE_MEMORY", {"raw": text}' in core_source
    assert 'intent, params = "EXPLAIN_MEMORY", {"raw": text}' in core_source
    assert 'if intent == "EXPLAIN_MEMORY"' in router_source

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

print("[PASS] AURA v2.1.1 R7-D2 live routing repair invariant")
print("[PASS] explicit Correction is forced to CREATE_MEMORY priority")
print("[PASS] version question selects version=1.1")
print("[PASS] mode question selects operating_mode values; generic prose word versions is allowed")
print("[PASS] local/cloud conflict surfaces both values with no invented certainty")
print("[PASS] explainability evidence is shared across Router/Core adapter instances")
print("[PASS] provenance follow-up phrase is forced to EXPLAIN_MEMORY priority")
print("[PASS] routing priority is WRITE -> EXPLAIN -> ANSWER")
print("[PASS] temporary SQLite only; no live memory row mutation")
