from __future__ import annotations

import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import AURA_VERSION
from action_receipts import (
    RECEIPT_STATUSES,
    ActionReceiptMissionAdapter,
    ActionReceiptService,
    ActionReceiptStore,
    CapabilityRegistry,
    ReceiptStateError,
)
from mission_engine import MissionEngine

assert AURA_VERSION == '0.9.4', AURA_VERSION

assert RECEIPT_STATUSES == (
    "requested",
    "waiting_confirmation",
    "denied",
    "running",
    "succeeded",
    "failed",
    "cancelled",
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
        return "UNKNOWN_DECISION"


with tempfile.TemporaryDirectory(prefix="aura_v089_receipts_") as td:
    db = Path(td) / "receipts.db"
    store = ActionReceiptStore(db)
    registry = CapabilityRegistry()
    service = ActionReceiptService(
        store=store,
        capability_registry=registry,
    )

    safe_context = registry.build_capability_context(
        capability_id="synthetic.safe",
        provider="synthetic",
        available=True,
        permission_state="granted",
        risk_tier="low",
        requires_confirmation=False,
        side_effect_class="none",
        evidence_required=True,
        health_state="healthy",
    )
    confirm_context = registry.build_capability_context(
        capability_id="synthetic.confirm",
        provider="synthetic",
        available=True,
        permission_state="granted",
        risk_tier="medium",
        requires_confirmation=True,
        side_effect_class="write",
        evidence_required=True,
        health_state="healthy",
    )
    registry.register(safe_context)
    registry.register(confirm_context)

    resolved = service.resolve_capability("synthetic.safe")
    assert resolved.capability_id == "synthetic.safe"
    assert resolved.available is True
    assert resolved.permission_state == "granted"

    unknown_cap = service.resolve_capability("unknown.capability")
    assert unknown_cap.available is False
    assert unknown_cap.requires_confirmation is True
    assert unknown_cap.permission_state == "unknown"

    security = FakeSecurity()
    executed = []

    def generic_executor(action, params):
        executed.append((action, dict(params)))
        if action == "fail.action":
            raise RuntimeError("synthetic failure")
        return {"ok": True, "action": action}

    # Non-mission success.
    success = service.execute_action(
        action="safe.action",
        tool_name="synthetic.safe",
        capability_context=safe_context,
        origin="direct.synthetic",
        params={"value": 7},
        security_engine=security,
        executor=generic_executor,
    )
    assert success.status == "succeeded"
    assert success.policy_decision == "ALLOW"
    assert success.result_digest
    assert success.params_digest
    assert success.completed_at
    assert success.duration_ms is not None

    # Terminal receipts are immutable.
    try:
        service.complete_receipt(
            success.receipt_id,
            result={"again": True},
        )
    except ReceiptStateError:
        pass
    else:
        raise AssertionError("terminal receipt must be immutable")

    # Denied action must not execute.
    before = len(executed)
    denied = service.execute_action(
        action="deny.action",
        tool_name="synthetic.safe",
        capability_context=safe_context,
        origin="direct.synthetic",
        params={"value": 8},
        security_engine=security,
        executor=generic_executor,
    )
    assert denied.status == "denied"
    assert denied.policy_decision == "DENY"
    assert len(executed) == before

    # Unknown policy decision fails closed.
    unknown = service.execute_action(
        action="safe.action",
        tool_name="synthetic.safe",
        capability_context=safe_context,
        origin="unknown-policy.synthetic",
        params={"value": 9},
        security_engine=UnknownSecurity(),
        executor=generic_executor,
    )
    assert unknown.status == "denied"
    assert unknown.policy_decision == "DENY"

    # Direct confirmation path creates waiting receipt without execution.
    before = len(executed)
    waiting = service.execute_action(
        action="needs.confirmation",
        tool_name="synthetic.confirm",
        capability_context=confirm_context,
        origin="direct.confirmation",
        params={"write": True},
        security_engine=security,
        executor=generic_executor,
        user_confirmed=False,
    )
    assert waiting.status == "waiting_confirmation"
    assert waiting.confirmation_state == "pending"
    assert len(executed) == before

    # Explicit cancellation path.
    cancelled = service.cancel_receipt(
        waiting.receipt_id,
        reason="synthetic cancellation",
    )
    assert cancelled.status == "cancelled"

    # Direct failure path.
    failed = service.execute_action(
        action="fail.action",
        tool_name="synthetic.safe",
        capability_context=safe_context,
        origin="direct.failure",
        params={"mode": "synthetic"},
        security_engine=security,
        executor=generic_executor,
    )
    assert failed.status == "failed"
    assert failed.error

    # Secrets must never be persisted raw.
    secret_value = "TOP-SECRET-VALUE-123"
    secret_receipt = service.execute_action(
        action="safe.action",
        tool_name="synthetic.safe",
        capability_context=safe_context,
        origin="direct.secret",
        params={
            "password": secret_value,
            "nested": {"token": secret_value},
            "ordinary": "visible",
        },
        security_engine=security,
        executor=lambda action, params: {
            "ok": True,
            "token": secret_value,
        },
    )
    assert secret_receipt.status == "succeeded"
    raw_db = db.read_bytes()
    assert secret_value.encode("utf-8") not in raw_db

    # ------------------------------------------------------------------
    # MissionEngine integration through adapters only.
    # ------------------------------------------------------------------
    tool_calls = []
    flaky = {"count": 0}

    def mission_executor(call):
        tool_calls.append(
            {
                "tool_name": call.tool_name,
                "action": call.action,
                "params": dict(call.params),
            }
        )
        if call.action == "flaky.action":
            flaky["count"] += 1
            if flaky["count"] == 1:
                raise RuntimeError("synthetic recoverable mission failure")
        return {
            "ok": True,
            "action": call.action,
        }

    mission_security = FakeSecurity()
    mission_engine = MissionEngine(
        security_engine=mission_security,
        tool_executor=mission_executor,
    )

    mission_registry = CapabilityRegistry()
    mission_registry.register(
        mission_registry.build_capability_context(
            capability_id="synthetic.confirm",
            provider="synthetic",
            available=True,
            permission_state="granted",
            risk_tier="medium",
            requires_confirmation=True,
            side_effect_class="write",
            evidence_required=True,
            health_state="healthy",
        )
    )
    mission_registry.register(
        mission_registry.build_capability_context(
            capability_id="synthetic.flaky",
            provider="synthetic",
            available=True,
            permission_state="granted",
            risk_tier="low",
            requires_confirmation=False,
            side_effect_class="compute",
            evidence_required=True,
            health_state="healthy",
        )
    )
    mission_registry.register(
        mission_registry.build_capability_context(
            capability_id="synthetic.safe",
            provider="synthetic",
            available=True,
            permission_state="granted",
            risk_tier="low",
            requires_confirmation=False,
            side_effect_class="none",
            evidence_required=True,
            health_state="healthy",
        )
    )

    mission_receipts = ActionReceiptService(
        store=store,
        capability_registry=mission_registry,
    )
    adapter = ActionReceiptMissionAdapter(
        mission_engine=mission_engine,
        receipt_service=mission_receipts,
        capability_registry=mission_registry,
    )

    mission = mission_engine.create_mission("Synthetic receipted mission")
    mission_engine.plan_mission(
        mission.mission_id,
        [
            {
                "key": "confirm",
                "tool_name": "synthetic.confirm",
                "action": "needs.confirmation",
                "params": {"target": "synthetic"},
                "max_attempts": 2,
            },
            {
                "key": "flaky",
                "tool_name": "synthetic.flaky",
                "action": "flaky.action",
                "depends_on": ["confirm"],
                "max_attempts": 2,
            },
            {
                "key": "finish",
                "tool_name": "synthetic.safe",
                "action": "safe.action",
                "depends_on": ["flaky"],
            },
        ],
    )
    mission_engine.start_mission(mission.mission_id)

    confirm_task = next(
        task
        for task in mission_engine.next_ready_tasks(mission.mission_id)
        if task.key == "confirm"
    )

    calls_before = len(tool_calls)
    adapter.execute_task(
        mission.mission_id,
        confirm_task.task_id,
        user_confirmed=False,
    )
    assert len(tool_calls) == calls_before
    pending_receipts = [
        r for r in store.list_receipts()
        if r.mission_id == mission.mission_id
        and r.task_id == confirm_task.task_id
    ]
    assert len(pending_receipts) == 1
    pending = pending_receipts[0]
    assert pending.status == "waiting_confirmation"

    # Same receipt resumes after explicit confirmation.
    adapter.execute_task(
        mission.mission_id,
        confirm_task.task_id,
        user_confirmed=True,
    )
    confirm_receipts = [
        r for r in store.list_receipts()
        if r.mission_id == mission.mission_id
        and r.task_id == confirm_task.task_id
    ]
    assert len(confirm_receipts) == 1
    confirm_receipt = confirm_receipts[0]
    assert confirm_receipt.receipt_id == pending.receipt_id
    assert confirm_receipt.status == "succeeded"
    assert confirm_receipt.confirmation_state == "confirmed"
    assert confirm_receipt.evidence_refs

    flaky_task = next(
        task
        for task in mission_engine.next_ready_tasks(mission.mission_id)
        if task.key == "flaky"
    )
    adapter.execute_task(mission.mission_id, flaky_task.task_id)

    first_flaky_receipts = [
        r for r in store.list_receipts()
        if r.mission_id == mission.mission_id
        and r.task_id == flaky_task.task_id
    ]
    assert len(first_flaky_receipts) == 1
    assert first_flaky_receipts[0].status == "failed"
    assert first_flaky_receipts[0].evidence_refs

    mission_engine.retry_task(mission.mission_id, flaky_task.task_id)
    adapter.execute_task(mission.mission_id, flaky_task.task_id)

    retry_receipts = [
        r for r in store.list_receipts()
        if r.mission_id == mission.mission_id
        and r.task_id == flaky_task.task_id
    ]
    assert len(retry_receipts) == 2
    assert retry_receipts[0].receipt_id != retry_receipts[1].receipt_id
    assert {r.status for r in retry_receipts} == {"failed", "succeeded"}

    finish_task = next(
        task
        for task in mission_engine.next_ready_tasks(mission.mission_id)
        if task.key == "finish"
    )
    adapter.execute_task(mission.mission_id, finish_task.task_id)
    mission_engine.complete(mission.mission_id)

    finish_receipt = next(
        r for r in store.list_receipts()
        if r.mission_id == mission.mission_id
        and r.task_id == finish_task.task_id
    )
    assert finish_receipt.status == "succeeded"
    assert finish_receipt.evidence_refs

    # Receipt schema and event ordering.
    with closing(sqlite3.connect(str(db))) as conn:
        receipt_tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        events = conn.execute(
            """
            SELECT receipt_id, sequence
            FROM action_receipt_events
            ORDER BY receipt_id, sequence
            """
        ).fetchall()

    assert {
        "action_receipts",
        "action_receipt_events",
    }.issubset(receipt_tables)

    with closing(sqlite3.connect(str(db))) as conn:
        receipt_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(action_receipts)")
        }
        receipt_indexes = {
            row[1]
            for row in conn.execute("PRAGMA index_list(action_receipts)")
        }

    assert "requested_at" in receipt_columns
    assert "idx_action_receipts_origin" in receipt_indexes

    by_receipt = {}
    for receipt_id, sequence in events:
        by_receipt.setdefault(receipt_id, []).append(int(sequence))
    for sequences in by_receipt.values():
        assert sequences == list(range(1, len(sequences) + 1))

    # Store round-trip.
    all_receipts = store.list_receipts()
    assert all_receipts
    for receipt in all_receipts:
        loaded = store.load(receipt.receipt_id)
        assert loaded is not None
        assert loaded.receipt_id == receipt.receipt_id
        assert loaded.params_digest == receipt.params_digest
        assert loaded.capability_context.get("capability_id")

    # Windows lock regression: every connection must be released.
    db.unlink()
    assert not db.exists()

print("[PASS] Action Receipts v0.8.9 synthetic lifecycle invariant")
raise SystemExit(0)
