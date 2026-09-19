from __future__ import annotations

import importlib
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

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
import services.core_bridge as core_bridge


class _Decision:
    allowed = True
    confirmation_required = False


class _Security:
    def authorize(self, *args, **kwargs):
        return _Decision()


tmp = tempfile.TemporaryDirectory(prefix="aura_v211_r4_")
db = None
try:
    db_path = Path(tmp.name) / "aura.db"
    db = Database(db_path)
    manager = MemoryManager(db)

    # ------------------------------------------------------------------
    # 1) Direct adapter UPDATE: 1.0 -> correction 1.1 must now commit.
    # ------------------------------------------------------------------
    adapter = ConversationMemoryIntegration(manager)

    first = adapter.plan_message(
        "Retiens que la version de TEST-R4 est 1.0.",
        observed_at="2026-09-11T12:00:00+00:00",
    )
    assert first.operation == "NEW"
    first_result = adapter.commit_explicit_fact(first)
    old_id = first_result["fact"]["fact_id"]

    update = adapter.plan_message(
        "Correction : la version actuelle de TEST-R4 est 1.1.",
        observed_at="2026-09-11T12:01:00+00:00",
    )
    assert update.operation == "UPDATE"
    updated = adapter.commit_explicit_fact(update)
    assert updated["status"] == "updated"
    assert updated["operation"] == "UPDATE"
    new_id = updated["fact"]["fact_id"]
    assert new_id != old_id

    old = adapter.kernel.v21_fact_by_id(old_id)
    new = adapter.kernel.v21_fact_by_id(new_id)
    assert old["status"] == "superseded"
    assert new["status"] == "active"
    assert new["object_text"] == "1.1"
    assert adapter.kernel.v21_list_conflicts(state="open") == []
    assert len(updated["resolved_conflicts"]) == 1
    assert updated["resolved_conflicts"][0]["state"] == "resolved"

    recall = adapter.recall_for_conversation(
        "TEST-R4 version 1.1",
        scope="user",
        at="2026-09-11T12:02:00+00:00",
        limit=20,
    )
    active_version_rows = [
        row for row in recall["results"]
        if row["fact"]["predicate"] == "version"
        and row["entity"]["canonical_name"] == "TEST-R4"
    ]
    assert active_version_rows
    assert all(row["fact"]["object_text"] == "1.1" for row in active_version_rows)

    # ------------------------------------------------------------------
    # 2) Router binding: canonical recognized writes, legacy fallback.
    # ------------------------------------------------------------------
    router = ActionRouter(
        None,
        None,
        None,
        _Security(),
        memory_manager=manager,
    )

    r1 = router._create_memory("Retiens que la version de ROUTER-R4 est 2.0.")
    assert "mémoire canonique" in r1
    r2 = router._create_memory(
        "Correction : la version actuelle de ROUTER-R4 est 2.1."
    )
    assert "mis à jour" in r2

    router_adapter = router._aura_v211_conversation_memory
    router_entity = router_adapter._find_entity(
        router_adapter.extract_explicit_fact(
            "Retiens que la version de ROUTER-R4 est 2.1."
        )
    )
    router_facts = router_adapter.kernel.v21_list_facts(
        subject_entity_id=router_entity["entity_id"],
        predicate="version",
        status="active",
        limit=20,
    )
    assert len(router_facts) == 1
    assert router_facts[0]["object_text"] == "2.1"

    legacy_before = db.conn.execute(
        "SELECT COUNT(*) FROM memories"
    ).fetchone()[0]
    legacy_reply = router._create_memory("je préfère le café très serré")
    legacy_after = db.conn.execute(
        "SELECT COUNT(*) FROM memories"
    ).fetchone()[0]
    assert legacy_after >= legacy_before + 1
    assert isinstance(legacy_reply, str) and legacy_reply.strip()

    # ------------------------------------------------------------------
    # 3) AuraCore additive accessor: one stable adapter / one kernel.
    # ------------------------------------------------------------------
    fake_core = object.__new__(AuraCore)
    fake_core.memory_manager = manager
    core_adapter_1 = fake_core.conversation_memory_v211()
    core_adapter_2 = fake_core.conversation_memory_v211()
    assert core_adapter_1 is core_adapter_2
    assert core_adapter_1.kernel is manager.v21_kernel()

    # ------------------------------------------------------------------
    # 4) MemoryService binding and exact legacy fallback availability.
    # ------------------------------------------------------------------
    service = object.__new__(core_bridge.MemoryService)
    service.core = SimpleNamespace(memory_manager=manager)

    # Avoid depending on MemoryService UI snapshot internals in this focused
    # write-path test.
    service.refresh = lambda *args, **kwargs: None

    s1 = service.remember(
        "Retiens que la version de SERVICE-R4 est 3.0.",
        memory_type="fact",
        importance=4,
    )
    assert s1["ok"] is True
    assert s1["canonical"] is True
    assert s1["operation"] == "NEW"

    s2 = service.remember(
        "Correction : la version actuelle de SERVICE-R4 est 3.1.",
        memory_type="fact",
        importance=4,
    )
    assert s2["canonical"] is True
    assert s2["operation"] == "UPDATE"
    assert s2["fact"]["object_text"] == "3.1"

    # Prove unrecognized content delegates to the preserved previous service
    # instead of being swallowed by the new adapter.
    saved_previous = core_bridge._AURA_V211_R4_PREVIOUS_MEMORYSERVICE_REMEMBER
    try:
        core_bridge._AURA_V211_R4_PREVIOUS_MEMORYSERVICE_REMEMBER = (
            lambda self, content, *, memory_type="", importance=3:
            {"ok": True, "legacy_fallback": True, "content": content}
        )
        fallback = service.remember(
            "texte libre non structuré pour compatibilité",
            memory_type="fact",
            importance=3,
        )
        assert fallback["legacy_fallback"] is True
    finally:
        core_bridge._AURA_V211_R4_PREVIOUS_MEMORYSERVICE_REMEMBER = saved_previous

    # ------------------------------------------------------------------
    # 5) Restart persistence on the same temporary DB.
    # ------------------------------------------------------------------
    if hasattr(db, "close"):
        db.close()
    else:
        db.conn.close()
    db = None

    db2 = Database(db_path)
    try:
        manager2 = MemoryManager(db2)
        adapter2 = ConversationMemoryIntegration(manager2)
        recall2 = adapter2.recall_for_conversation(
            "TEST-R4 version 1.1",
            scope="user",
            at="2026-09-11T12:03:00+00:00",
            limit=20,
        )
        rows2 = [
            row for row in recall2["results"]
            if row["fact"]["predicate"] == "version"
            and row["entity"]["canonical_name"] == "TEST-R4"
        ]
        assert rows2
        assert all(row["fact"]["object_text"] == "1.1" for row in rows2)

        entity2 = adapter2._find_entity(
            adapter2.extract_explicit_fact(
                "Retiens que la version de TEST-R4 est 1.1."
            )
        )
        active2 = adapter2.kernel.v21_list_facts(
            subject_entity_id=entity2["entity_id"],
            predicate="version",
            status="active",
            limit=20,
        )
        assert len(active2) == 1
        assert active2[0]["object_text"] == "1.1"
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

print("[PASS] AURA v2.1.1 R4 UPDATE + runtime write binding invariant")
print("[PASS] explicit correction 1.0 -> 1.1 canonically supersedes 1.0")
print("[PASS] supersession uses existing conflict open/resolve primitives")
print("[PASS] old fact becomes superseded; new fact is sole active current value")
print("[PASS] no open conflict remains after explicit correction")
print("[PASS] canonical recall returns current 1.1")
print("[PASS] router recognized memory writes are canonical-first")
print("[PASS] router unrecognized free text preserves exact legacy fallback")
print("[PASS] AuraCore exposes one stable ConversationMemoryIntegration adapter")
print("[PASS] MemoryService recognized writes are canonical-first")
print("[PASS] MemoryService unrecognized content preserves legacy fallback")
print("[PASS] corrected value persists after complete DB reopen")
print("[PASS] temporary SQLite only; no live memory row mutation")
