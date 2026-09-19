from __future__ import annotations

import sqlite3
from contextlib import closing
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import AURA_VERSION
from mission_engine import (
    MISSION_STATES,
    TASK_STATES,
    MissionEngine,
    MissionGraphError,
    SQLiteMissionStore,
)

assert AURA_VERSION == '0.9.4', AURA_VERSION

assert MISSION_STATES == (
    "draft", "planned", "ready", "running", "waiting_confirmation",
    "blocked", "recovering", "completed", "failed", "cancelled",
)
assert TASK_STATES == (
    "pending", "ready", "running", "waiting_confirmation",
    "succeeded", "failed", "skipped", "cancelled",
)


class FakeSecurity:
    def __init__(self):
        self.calls = []

    def authorize(self, action, params, user_confirmed=False):
        self.calls.append(
            {
                "action": action,
                "params": dict(params),
                "user_confirmed": bool(user_confirmed),
            }
        )
        if action == "needs.confirmation" and not user_confirmed:
            return "REQUIRE_CONFIRMATION"
        if action == "deny.action":
            return "DENY"
        return "ALLOW"


class UnknownSecurity:
    def authorize(self, action, params, user_confirmed=False):
        return "SOMETHING_UNKNOWN"


with tempfile.TemporaryDirectory(prefix="aura_v088_mission_") as td:
    db = Path(td) / "mission_test.db"
    security = FakeSecurity()
    executor_calls = []
    flaky = {"count": 0}

    def executor(call):
        executor_calls.append(
            {
                "tool_name": call.tool_name,
                "action": call.action,
                "params": dict(call.params),
            }
        )
        if call.action == "flaky.action":
            flaky["count"] += 1
            if flaky["count"] == 1:
                raise RuntimeError("synthetic recoverable failure")
        return {
            "ok": True,
            "tool": call.tool_name,
            "action": call.action,
            "params": dict(call.params),
        }

    store = SQLiteMissionStore(db)
    engine = MissionEngine(
        security_engine=security,
        tool_executor=executor,
        store=store,
        planning_context_provider=lambda goal: {
            "source": "MemoryKernel-compatible planning context",
            "goal_id": goal.goal_id,
        },
    )

    m1 = engine.create_mission(
        "Prepare a synthetic audited mission",
        ["all required tasks succeed", "evidence exists"],
    )
    m1_again = engine.create_mission(
        "Prepare a synthetic audited mission",
        ["all required tasks succeed", "evidence exists"],
    )
    assert m1.mission_id == m1_again.mission_id
    assert store.count() == 1

    # R1 Windows SQLite handle regression.
    # SQLiteMissionStore must release every connection immediately so a
    # temporary database can be deleted while the store object still exists.
    lock_probe_db = Path(td) / "lock_probe.db"
    lock_probe_store = SQLiteMissionStore(lock_probe_db)
    lock_probe_mission = MissionEngine(
        security_engine=security,
        tool_executor=executor,
        store=lock_probe_store,
    ).create_mission("SQLite handle release synthetic")
    assert lock_probe_store.load(lock_probe_mission.mission_id) is not None
    assert lock_probe_store.count() == 1
    lock_probe_db.unlink()
    assert not lock_probe_db.exists()

    specs = [
        {
            "key": "collect",
            "title": "Collect synthetic input",
            "tool_name": "synthetic.collector",
            "action": "needs.confirmation",
            "params": {"scope": "synthetic"},
            "max_attempts": 2,
        },
        {
            "key": "analyze",
            "title": "Analyze synthetic input",
            "tool_name": "synthetic.analyzer",
            "action": "flaky.action",
            "params": {"mode": "test"},
            "depends_on": ["collect"],
            "max_attempts": 2,
        },
        {
            "key": "deliver",
            "title": "Deliver synthetic result",
            "tool_name": "synthetic.writer",
            "action": "safe.action",
            "params": {"destination": "synthetic"},
            "depends_on": ["analyze"],
        },
    ]

    engine.plan_mission(
        m1.mission_id,
        specs,
        planning_context={"request": "synthetic only"},
    )
    engine.start_mission(m1.mission_id)

    ready = engine.next_ready_tasks(m1.mission_id)
    collect = next(task for task in ready if task.key == "collect")
    before_calls = len(executor_calls)

    collect = engine.execute_task(m1.mission_id, collect.task_id)
    assert collect.status == "waiting_confirmation"
    assert engine.get_mission(m1.mission_id).status == "waiting_confirmation"
    assert len(executor_calls) == before_calls
    assert security.calls[-1]["user_confirmed"] is False

    collect = engine.execute_task(
        m1.mission_id,
        collect.task_id,
        user_confirmed=True,
    )
    assert collect.status == "succeeded"
    assert security.calls[-1]["user_confirmed"] is True
    assert collect.evidence_ids

    ready = engine.next_ready_tasks(m1.mission_id)
    analyze = next(task for task in ready if task.key == "analyze")
    analyze = engine.execute_task(m1.mission_id, analyze.task_id)
    assert analyze.status == "failed"
    assert analyze.attempts == 1
    assert engine.get_mission(m1.mission_id).status == "recovering"
    failure_evidence = tuple(analyze.evidence_ids)
    assert failure_evidence

    analyze = engine.retry_task(m1.mission_id, analyze.task_id)
    assert analyze.status == "ready"
    analyze = engine.execute_task(m1.mission_id, analyze.task_id)
    assert analyze.status == "succeeded"
    assert analyze.attempts == 2
    assert len(analyze.evidence_ids) > len(failure_evidence)

    ready = engine.next_ready_tasks(m1.mission_id)
    deliver = next(task for task in ready if task.key == "deliver")
    deliver = engine.execute_task(m1.mission_id, deliver.task_id)
    assert deliver.status == "succeeded"
    assert deliver.evidence_ids

    mission = engine.complete(m1.mission_id)
    assert mission.status == "completed"

    reloaded = store.load(m1.mission_id)
    assert reloaded is not None
    assert reloaded.status == "completed"
    assert len(reloaded.evidence) >= 6

    with closing(sqlite3.connect(str(db))) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert {
        "mission_engine_missions",
        "mission_engine_events",
        "mission_engine_evidence",
    }.issubset(tables)

    cycle = engine.create_mission("Cycle rejection synthetic")
    try:
        engine.plan_mission(
            cycle.mission_id,
            [
                {
                    "key": "a",
                    "tool_name": "synthetic",
                    "action": "safe.action",
                    "depends_on": ["b"],
                },
                {
                    "key": "b",
                    "tool_name": "synthetic",
                    "action": "safe.action",
                    "depends_on": ["a"],
                },
            ],
        )
    except MissionGraphError:
        pass
    else:
        raise AssertionError("cycle must be rejected")

    repl = engine.create_mission("Replan synthetic")
    engine.plan_mission(
        repl.mission_id,
        [
            {"key": "done", "tool_name": "synthetic", "action": "safe.action"},
            {
                "key": "future",
                "tool_name": "synthetic",
                "action": "safe.action",
                "depends_on": ["done"],
            },
        ],
    )
    engine.start_mission(repl.mission_id)
    done = next(task for task in engine.next_ready_tasks(repl.mission_id) if task.key == "done")
    engine.execute_task(repl.mission_id, done.task_id)
    done_after = engine.get_mission(repl.mission_id).tasks[done.task_id]
    frozen_evidence = tuple(done_after.evidence_ids)

    replanned = engine.replan(
        repl.mission_id,
        [
            {
                "key": "replacement",
                "tool_name": "synthetic",
                "action": "safe.action",
                "depends_on": ["done"],
            }
        ],
    )
    preserved = next(task for task in replanned.tasks.values() if task.key == "done")
    assert preserved.status == "succeeded"
    assert tuple(preserved.evidence_ids) == frozen_evidence

    try:
        engine.replan(
            repl.mission_id,
            [{"key": "done", "tool_name": "synthetic", "action": "safe.action"}],
        )
    except MissionGraphError:
        pass
    else:
        raise AssertionError("replan must not replace succeeded task")

    unknown_calls = []
    unknown_engine = MissionEngine(
        security_engine=UnknownSecurity(),
        tool_executor=lambda call: unknown_calls.append(call),
        store=SQLiteMissionStore(Path(td) / "unknown.db"),
    )
    denied = unknown_engine.create_mission("Unknown policy synthetic")
    unknown_engine.plan_mission(
        denied.mission_id,
        [{"key": "deny", "tool_name": "synthetic", "action": "safe.action"}],
    )
    unknown_engine.start_mission(denied.mission_id)
    deny_task = unknown_engine.next_ready_tasks(denied.mission_id)[0]
    deny_task = unknown_engine.execute_task(denied.mission_id, deny_task.task_id)
    assert deny_task.status == "failed"
    assert deny_task.error == "policy_denied"
    assert unknown_calls == []

    cancelled = engine.create_mission("Cancellation synthetic")
    engine.plan_mission(
        cancelled.mission_id,
        [{"key": "pending", "tool_name": "synthetic", "action": "safe.action"}],
    )
    engine.cancel(cancelled.mission_id)
    assert engine.get_mission(cancelled.mission_id).status == "cancelled"

    # R2 definitive Windows cleanup assertion for the primary mission DB.
    # No SQLite handle may survive the complete synthetic lifecycle.
    db.unlink()
    assert not db.exists()

print("[PASS] MissionEngine v0.8.8 synthetic lifecycle invariant")
raise SystemExit(0)
