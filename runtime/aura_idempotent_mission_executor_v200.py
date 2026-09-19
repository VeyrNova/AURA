"""AURA A200-R11 R2 canonical Task schema repair.

R2 fixes the only defect exposed by R11-R1: MissionEngine Task stores canonical
dependency task ids in `task.dependencies`, while `depends_on` exists only in
input task specifications before MissionEngine normalization.

R11-R1 pre-execution attempt arming remains intact.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from mission_engine import MissionEngine, Task, ToolCall
from runtime.aura_crash_recovery_v200 import (
    A200CrashRecoveryJournal,
    A200CrashSafeMissionExecutor,
    CrashRecoveryResult,
)
from runtime.aura_execution_idempotency_v200 import (
    A200ExecutionIntentLedger,
    IdempotencyConflict,
    request_digest,
    logical_key,
)


A200_R11_MARKER = "AURA_A200_R11_IDEMPOTENCY_GUARD_MISSION_EXECUTOR_INTEGRATION_V1"
A200_R11_R1_MARKER = "AURA_A200_R11_R1_ATTEMPT_CONTEXT_BINDING_REPAIR_V1"
A200_R11_R2_MARKER = "AURA_A200_R11_R2_CANONICAL_TASK_SCHEMA_REPAIR_V1"

MISSION_EXECUTOR_IDEMPOTENCY_REQUIRED = True
ATTEMPT_SCOPED_INTENT_KEYS = True
PRE_EXECUTION_ATTEMPT_ARMING_REQUIRED = True
CANONICAL_TASK_DEPENDENCIES_FIELD = "dependencies"

DUPLICATE_DISPATCH_ENABLED = False
LEASE_STEAL_ENABLED = False
AUTONOMOUS_RETRY_ENABLED = False
AUTONOMOUS_MUTATION_ENABLED = False
DESTRUCTIVE_EXECUTION_ENABLED = False


class R11ExecutionBindingError(RuntimeError):
    pass


@dataclass(frozen=True)
class ArmedAttemptContext:
    mission_id: str
    task_id: str
    plan_revision: int
    attempt: int
    contract_digest: str


def mission_task_contract_digest(mission: Any, task: Task) -> str:
    """Digest only canonical persisted MissionEngine task-contract fields."""
    from hashlib import sha256
    import json

    if mission.plan is None:
        raise R11ExecutionBindingError("mission has no canonical plan")

    if not hasattr(task, CANONICAL_TASK_DEPENDENCIES_FIELD):
        raise R11ExecutionBindingError(
            "canonical MissionEngine Task.dependencies field is unavailable"
        )

    payload = {
        "mission_id": mission.mission_id,
        "plan_id": mission.plan.plan_id,
        "plan_revision": mission.plan.revision,
        "task_id": task.task_id,
        "task_key": task.key,
        "title": task.title,
        "tool_name": task.tool_call.tool_name,
        "action": task.tool_call.action,
        "params": dict(task.tool_call.params or {}),
        "dependencies": list(task.dependencies),
        "required": bool(task.required),
        "max_attempts": int(task.max_attempts),
    }
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(raw.encode("utf-8")).hexdigest()


def attempt_scoped_intent_key(
    *,
    mission_id: str,
    task_id: str,
    action: str,
    plan_revision: int,
    attempt: int,
) -> str:
    if int(attempt) < 1:
        raise R11ExecutionBindingError("attempt must be >= 1")
    return logical_key(
        mission_id=mission_id,
        task_id=f"{task_id}::attempt::{int(attempt)}",
        action=action,
        plan_revision=int(plan_revision),
    )


class A200IdempotentCrashSafeMissionExecutor(A200CrashSafeMissionExecutor):
    """R9 executor with R10 durable dispatch-once semantics embedded."""

    def __init__(
        self,
        *,
        mission_engine: MissionEngine,
        read_binding: Any,
        mutation_binding: Any,
        crash_journal: A200CrashRecoveryJournal,
        intent_ledger: A200ExecutionIntentLedger,
        owner_id: str,
        after_dispatch_hook: Callable[[ToolCall, dict[str, Any]], None] | None = None,
    ) -> None:
        super().__init__(
            mission_engine=mission_engine,
            read_binding=read_binding,
            mutation_binding=mutation_binding,
            crash_journal=crash_journal,
        )
        self.intent_ledger = intent_ledger
        self.owner_id = str(owner_id or "").strip()
        if not self.owner_id:
            raise R11ExecutionBindingError("non-empty execution owner_id required")
        self.after_dispatch_hook = after_dispatch_hook
        self._armed_attempt: ArmedAttemptContext | None = None
        self.last_idempotency_disposition: str | None = None
        self.last_intent_key: str | None = None
        self.last_attempt: int | None = None

    def _arm_attempt_context(self, mission_id: str, task_id: str) -> ArmedAttemptContext:
        mission = self.engine.get_mission(mission_id)
        if mission.plan is None:
            raise R11ExecutionBindingError("MissionEngine mission has no canonical plan")

        task = mission.tasks.get(task_id)
        if task is None:
            raise R11ExecutionBindingError("MissionEngine task missing before execution")

        attempt = int(task.attempts) + 1
        if attempt < 1:
            raise R11ExecutionBindingError("invalid next MissionEngine attempt")
        if attempt > int(task.max_attempts):
            raise R11ExecutionBindingError(
                f"next attempt {attempt} exceeds task max_attempts={task.max_attempts}"
            )

        return ArmedAttemptContext(
            mission_id=mission_id,
            task_id=task_id,
            plan_revision=int(mission.plan.revision),
            attempt=attempt,
            contract_digest=mission_task_contract_digest(mission, task),
        )

    def _execute_task(
        self,
        mission_id: str,
        task_id: str,
        *,
        user_confirmed: bool,
    ) -> Task:
        if self._armed_attempt is not None:
            raise R11ExecutionBindingError("nested R11 attempt context refused")

        self._armed_attempt = self._arm_attempt_context(mission_id, task_id)
        try:
            return super()._execute_task(
                mission_id,
                task_id,
                user_confirmed=user_confirmed,
            )
        finally:
            self._armed_attempt = None

    def _active_identity(self, call: ToolCall) -> tuple[Any, Task, int, str, str]:
        mission_id = self._active_mission_id
        task_id = self._active_task_id
        if not mission_id or not task_id:
            raise R11ExecutionBindingError("MissionEngine task context is not armed")

        mission = self.engine.get_mission(mission_id)
        if mission.plan is None:
            raise R11ExecutionBindingError("MissionEngine task has no canonical plan")
        task = mission.tasks.get(task_id)
        if task is None:
            raise R11ExecutionBindingError("active MissionEngine task missing")

        if str(task.tool_call.action) != str(call.action):
            raise R11ExecutionBindingError(
                "tool-call action differs from canonical MissionEngine task"
            )
        if dict(task.tool_call.params or {}) != dict(call.params or {}):
            raise R11ExecutionBindingError(
                "tool-call params differ from canonical MissionEngine task"
            )

        armed = self._armed_attempt
        if armed is not None:
            if armed.mission_id != mission_id or armed.task_id != task_id:
                raise R11ExecutionBindingError("armed attempt context identity mismatch")
            if armed.plan_revision != int(mission.plan.revision):
                raise R11ExecutionBindingError("armed attempt plan revision mismatch")
            current_contract = mission_task_contract_digest(mission, task)
            if current_contract != armed.contract_digest:
                raise R11ExecutionBindingError(
                    "canonical task contract changed during execution"
                )
            attempt = armed.attempt
            contract_digest = armed.contract_digest
        else:
            # Stale-replay verification path only. Never invent a future attempt.
            attempt = int(task.attempts)
            if attempt < 1:
                raise R11ExecutionBindingError(
                    "no armed attempt and no persisted attempt available"
                )
            contract_digest = mission_task_contract_digest(mission, task)

        key = attempt_scoped_intent_key(
            mission_id=mission_id,
            task_id=task_id,
            action=str(call.action),
            plan_revision=int(mission.plan.revision),
            attempt=attempt,
        )
        req_digest = request_digest(
            action=str(call.action),
            params=dict(call.params or {}),
            plan_digest=contract_digest,
        )
        self.last_attempt = attempt
        return mission, task, attempt, key, req_digest

    def tool_executor(self, call: ToolCall) -> dict[str, Any]:
        mission, task, attempt, key, req_digest = self._active_identity(call)
        self.last_intent_key = key

        claim = self.intent_ledger.claim(
            intent_key=key,
            mission_id=mission.mission_id,
            task_id=task.task_id,
            action=str(call.action),
            plan_revision=int(mission.plan.revision),
            request_digest=req_digest,
            owner_id=self.owner_id,
        )

        if claim.disposition == "duplicate_succeeded":
            import json
            cached = (
                {}
                if not claim.record.result_json
                else dict(json.loads(claim.record.result_json))
            )
            cached["idempotency_disposition"] = "duplicate_suppressed"
            cached["idempotency_intent_key"] = key
            cached["idempotency_attempt"] = attempt
            cached["receipt_id"] = claim.record.receipt_id
            self.last_idempotency_disposition = "duplicate_suppressed"
            return cached

        try:
            result = dict(super().tool_executor(call))

            if self.after_dispatch_hook is not None:
                self.after_dispatch_hook(call, result)

            receipt_id = str(result.get("receipt_id") or "")
            status = str(result.get("status") or "")
            ok = bool(result.get("ok"))
            if not receipt_id or status != "succeeded" or not ok:
                raise IdempotencyConflict(
                    "MissionEngine dispatch must return canonical ok/succeeded receipt"
                )

            self.intent_ledger.complete_success(
                intent_key=key,
                owner_id=self.owner_id,
                receipt_id=receipt_id,
                result=result,
            )
            result["idempotency_disposition"] = "executed"
            result["idempotency_intent_key"] = key
            result["idempotency_attempt"] = attempt
            self.last_idempotency_disposition = "executed"
            return result

        except Exception as exc:
            current = self.intent_ledger.get(key)
            if (
                current is not None
                and current.state == "running"
                and current.owner_id == self.owner_id
            ):
                self.intent_ledger.mark_failed(
                    intent_key=key,
                    owner_id=self.owner_id,
                    error=exc,
                )
            self.last_idempotency_disposition = "failed"
            raise

    def recover_after_restart(self, mission_id: str) -> CrashRecoveryResult:
        pending = self.crash_journal.get_pending(mission_id)
        if pending is None:
            return super().recover_after_restart(mission_id)

        mission = self.engine.get_mission(mission_id)
        task = mission.tasks.get(pending.task_id)
        if task is None or mission.plan is None:
            raise R11ExecutionBindingError(
                "pending crash journal cannot bind to MissionEngine task"
            )

        attempt = int(task.attempts)
        if attempt < 1:
            raise R11ExecutionBindingError(
                "crashed MissionEngine task has invalid persisted attempt"
            )

        contract_digest = mission_task_contract_digest(mission, task)
        key = attempt_scoped_intent_key(
            mission_id=mission_id,
            task_id=task.task_id,
            action=str(task.tool_call.action),
            plan_revision=int(mission.plan.revision),
            attempt=attempt,
        )
        req_digest = request_digest(
            action=str(task.tool_call.action),
            params=dict(task.tool_call.params or {}),
            plan_digest=contract_digest,
        )

        result = super().recover_after_restart(mission_id)

        record = self.intent_ledger.get(key)
        if record is None:
            raise R11ExecutionBindingError(
                "crash-recovered task has no R10 intent record"
            )

        if record.state == "running":
            self.intent_ledger.reconcile_recovered(
                intent_key=key,
                request_digest=req_digest,
                recovery_receipt_id=result.restore_receipt_id,
            )
        elif record.state == "succeeded":
            pass
        else:
            raise R11ExecutionBindingError(
                f"unexpected intent state during crash recovery: {record.state}"
            )

        return result


def assert_r11_safety_contract() -> None:
    if not MISSION_EXECUTOR_IDEMPOTENCY_REQUIRED:
        raise RuntimeError("Mission executor idempotency must remain mandatory")
    if not ATTEMPT_SCOPED_INTENT_KEYS:
        raise RuntimeError("attempt-scoped intent keys are required")
    if not PRE_EXECUTION_ATTEMPT_ARMING_REQUIRED:
        raise RuntimeError("pre-execution attempt arming must remain mandatory")
    if CANONICAL_TASK_DEPENDENCIES_FIELD != "dependencies":
        raise RuntimeError("canonical Task dependency field must remain dependencies")
    if DUPLICATE_DISPATCH_ENABLED or LEASE_STEAL_ENABLED:
        raise RuntimeError("duplicate dispatch / lease stealing must remain disabled")
    if AUTONOMOUS_RETRY_ENABLED or AUTONOMOUS_MUTATION_ENABLED:
        raise RuntimeError("autonomous retry/mutation must remain disabled")
    if DESTRUCTIVE_EXECUTION_ENABLED:
        raise RuntimeError("destructive execution must remain disabled")
