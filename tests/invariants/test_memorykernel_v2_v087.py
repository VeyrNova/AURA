from __future__ import annotations

import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory.kernel_v2 import MemoryKernelV2, MemoryScope, MemoryType
from memory.manager import MemoryManager


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="microseconds")


with tempfile.TemporaryDirectory(prefix="aura-memorykernel-v2-") as tmp:
    db = Path(tmp) / "synthetic.db"
    kernel = MemoryKernelV2(db)
    kernel.ensure_schema()

    working = kernel.remember(
        "temporary working context",
        memory_type=MemoryType.WORKING,
        scope=MemoryScope.SESSION,
        scope_id="session-1",
        provenance={"source": "synthetic"},
    )
    episodic = kernel.remember(
        "met Alice at project kickoff",
        memory_type="episodic",
        scope="session",
        scope_id="session-1",
        provenance={"source": "synthetic", "event": "kickoff"},
    )
    semantic_a = kernel.remember(
        "AURA project uses a local-first architecture",
        memory_type="semantic",
        scope="project",
        scope_id="AURA",
        provenance={"source": "synthetic-a"},
    )
    semantic_b = kernel.remember(
        "AURA project preserves certified baselines",
        memory_type="semantic",
        scope="project",
        scope_id="AURA",
        provenance={"source": "synthetic-b"},
    )
    preference = kernel.remember(
        "prefers concise technical reports",
        memory_type="preference",
        scope="user",
        provenance={"source": "synthetic"},
    )
    project = kernel.remember(
        "MemoryKernel v2 is the active roadmap milestone",
        memory_type="project",
        scope="project",
        scope_id="AURA",
        provenance={"source": "synthetic"},
    )

    assert working.memory_type is MemoryType.WORKING
    assert episodic.memory_type is MemoryType.EPISODIC
    assert preference.scope_id == "default"
    assert project.memory_type is MemoryType.PROJECT

    hits = kernel.retrieve(
        "local architecture",
        memory_types=["semantic"],
        scope="project",
        scope_id="AURA",
        limit=10,
    )
    assert hits and hits[0].memory_id == semantic_a.memory_id
    assert hits[0].provenance["source"] == "synthetic-a"

    updated = kernel.update(
        project.memory_id,
        content="MemoryKernel v2 is implemented transactionally",
        provenance={"updated_by": "synthetic-test"},
    )
    assert updated.version == 2
    assert updated.provenance["lineage"]["previous_version"] == 1

    merged = kernel.merge(
        [semantic_a.memory_id, semantic_b.memory_id],
        provenance={"reason": "synthetic-consolidation"},
    )
    assert merged.memory_type is MemoryType.SEMANTIC
    assert len(merged.provenance["merged_from"]) == 2
    assert kernel.get(semantic_a.memory_id) is None
    merged_source = kernel.get(semantic_a.memory_id, include_inactive=True, include_sensitive=True)
    assert merged_source is not None and merged_source.status == "merged"
    assert merged_source.merged_into_id == merged.memory_id

    expiring = kernel.remember(
        "temporary episodic item",
        memory_type="episodic",
        scope="session",
        scope_id="session-2",
        provenance={"source": "synthetic"},
        expires_at=iso(datetime.now(timezone.utc) - timedelta(seconds=1)),
    )
    expired_ids = kernel.expire()
    assert expiring.memory_id in expired_ids
    assert kernel.get(expiring.memory_id) is None
    expired = kernel.get(expiring.memory_id, include_inactive=True, include_sensitive=True)
    assert expired is not None and expired.status == "expired"

    forgotten_id = preference.memory_id
    assert kernel.forget(forgotten_id) is True
    assert kernel.get(forgotten_id, include_inactive=True, include_sensitive=True) is None
    actions = kernel.audit_actions(forgotten_id)
    assert actions and actions[-1]["action"] == "forget"
    assert "content" not in actions[-1]["detail"]

    denied = MemoryKernelV2(Path(tmp) / "guarded.db", policy_guard=lambda action, payload: False)
    try:
        denied.remember("must fail", memory_type="semantic", scope="user", provenance={"source": "synthetic"})
        raise AssertionError("policy guard did not fail closed")
    except PermissionError:
        pass

    def broken_guard(action, payload):
        raise RuntimeError("synthetic guard failure")

    broken = MemoryKernelV2(Path(tmp) / "broken.db", policy_guard=broken_guard)
    try:
        broken.remember("must fail closed", memory_type="semantic", scope="user", provenance={"source": "synthetic"})
        raise AssertionError("policy guard exception did not fail closed")
    except PermissionError:
        pass

    conn = sqlite3.connect(str(db))
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "memory_kernel_v2_records" in tables
        assert "memory_kernel_v2_audit" in tables
    finally:
        conn.close()

assert getattr(MemoryManager, "MEMORY_KERNEL_VERSION", None) == "2"
for name in ("memorykernel_v2", "remember_v2", "retrieve_v2", "update_v2", "merge_v2", "forget_v2", "expire_v2"):
    assert hasattr(MemoryManager, name), name

print("[PASS] MemoryKernel v2 synthetic lifecycle invariant")
raise SystemExit(0)
