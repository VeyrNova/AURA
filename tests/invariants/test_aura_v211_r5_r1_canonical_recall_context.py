from __future__ import annotations

import inspect
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
from core.aura_core import AuraCore


def canonical_value_lines(context: str, subject: str, predicate: str) -> list[str]:
    prefix = f"- {subject} | {predicate} = "
    return [
        line.strip()
        for line in str(context or "").splitlines()
        if line.strip().startswith(prefix)
    ]


tmp = tempfile.TemporaryDirectory(prefix="aura_v211_r5_r1_")
db = None
try:
    db_path = Path(tmp.name) / "aura.db"
    db = Database(db_path)
    manager = MemoryManager(db)

    core = object.__new__(AuraCore)
    core.memory_manager = manager
    adapter = core.conversation_memory_v211()

    assert isinstance(adapter, ConversationMemoryIntegration)
    assert adapter.kernel is manager.v21_kernel()

    # Legacy-only fallback must still work.
    manager.remember(
        "je préfère le café très serré",
        memory_type="preference",
        source="explicit_user",
        importance=4,
    )
    fallback = core._aura_v211_r5_memory_context(
        "Quelle est ma préférence pour le café ?",
        memory_limit=6,
        compact=False,
    )
    assert fallback
    assert "café" in fallback.casefold()

    # Stale legacy 1.0.
    manager.remember(
        "La version de TEST-R5 est 1.0",
        memory_type="fact",
        source="explicit_user",
        importance=4,
    )

    # Canonical 1.0 -> explicit correction 1.1.
    first = adapter.plan_message(
        "Retiens que la version de TEST-R5 est 1.0.",
        observed_at="2026-09-11T13:00:00+00:00",
    )
    assert first.operation == "NEW"
    adapter.commit_explicit_fact(first)

    correction = adapter.plan_message(
        "Correction : la version actuelle de TEST-R5 est 1.1.",
        observed_at="2026-09-11T13:01:00+00:00",
    )
    assert correction.operation == "UPDATE"
    update_result = adapter.commit_explicit_fact(correction)
    assert update_result["fact"]["object_text"] == "1.1"

    context = core._aura_v211_r5_memory_context(
        "Quelle est la version actuelle de TEST-R5 ?",
        memory_limit=8,
        compact=False,
    )

    lines = canonical_value_lines(context, "TEST-R5", "version")
    assert lines, context

    # Corrected assertion: inspect canonical fact lines, not arbitrary numeric
    # substrings such as "confiance=1.00".
    assert any("= 1.1" in line for line in lines), context
    assert not any("= 1.0" in line for line in lines), context
    assert "AURA MEMORY v2.1" in context
    assert "priment sur tout ancien souvenir legacy contradictoire" in context

    # The numeric metadata confidence=1.00 is allowed and must not be confused
    # with a stale semantic value 1.0.
    assert "confiance=1.00" in context

    source = inspect.getsource(AuraCore.build_llm_messages)
    assert "self._aura_v211_r5_memory_context(" in source
    assert (
        "memory_context = self.memory_manager.render_for_prompt(memories, compact=compact)"
        not in source
    )

    manager.set_private_mode(True)
    private_context = core._aura_v211_r5_memory_context(
        "Quelle est la version actuelle de TEST-R5 ?",
        memory_limit=8,
        compact=False,
    )
    assert private_context == ""
    manager.set_private_mode(False)

    if hasattr(db, "close"):
        db.close()
    else:
        db.conn.close()
    db = None

    db2 = Database(db_path)
    try:
        manager2 = MemoryManager(db2)
        core2 = object.__new__(AuraCore)
        core2.memory_manager = manager2
        context2 = core2._aura_v211_r5_memory_context(
            "Quelle est la version actuelle de TEST-R5 ?",
            memory_limit=8,
            compact=False,
        )
        lines2 = canonical_value_lines(context2, "TEST-R5", "version")
        assert any("= 1.1" in line for line in lines2), context2
        assert not any("= 1.0" in line for line in lines2), context2
    finally:
        if hasattr(db2, "close"):
            db2.close()
        else:
            db2.conn.close()

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

print("[PASS] AURA v2.1.1 R5-R1 canonical recall-context invariant")
print("[PASS] legacy fallback works when canonical recall is empty")
print("[PASS] canonical TEST-R5 version line contains 1.1")
print("[PASS] canonical TEST-R5 version line does NOT contain stale 1.0")
print("[PASS] confidence=1.00 metadata no longer causes a false stale-value failure")
print("[PASS] build_llm_messages uses canonical-first context helper")
print("[PASS] private mode suppresses prompt memory")
print("[PASS] canonical priority survives complete DB reopen")
print("[PASS] temporary SQLite only; no live memory row mutation")
