"""AURA A200-R7 supervised multi-step E2E mission execution.

This adapter does not replace MissionEngine. It binds the canonical MissionEngine
task executor to the already accepted A200 R4/R5 execution gates.

Accepted mission shape:
  read foreground
  -> one reversible minimize (explicit MissionEngine confirmation)
  -> read foreground
  -> restore exact W132 recovery preimage
  -> read foreground

The reversible mutation is also re-bound to an exact A200-R2 plan digest before
R5 dispatch. If a task fails while an unconsumed recovery token exists, the
adapter performs an immediate fail-safe W132 restoration outside the blocked DAG,
records emergency_recovery evidence in MissionEngine, and cancels the remainder.

No destructive capability, raw shell, direct Win32 call, or autonomous retry is
introduced here.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from mission_engine import MissionEngine, Task, ToolCall
from runtime.aura_autonomous_supervisor_v200 import ApprovalGrant, SupervisedPlan
from runtime.aura_readonly_pc_execution_binding_v200 import A200ReadOnlyPcExecutionBinding
from runtime.aura_reversible_mutation_binding_v200 import (
    A200RecoveryToken,
    A200ReversibleMutationBinding,
)


A200_R7_MARKER = "AURA_A200_R7_SUPERVISED_MULTI_STEP_E2E_MISSION_V1"

READ_ACTIONS = frozenset({
    "pc.discover_windows",
    "pc.discover_processes",
    "pc.get_foreground_window",
})
REVERSIBLE_ACTION = "pc.minimize_window"
RESTORE_ACTION = "pc.restore_window_state"

AUTONOMOUS_MULTI_MUTATION_ENABLED = False
AUTONOMOUS_RETRY_ENABLED = False
DESTRUCTIVE_EXECUTION_ENABLED = False
FAIL_SAFE_RECOVERY_REQUIRED = True


class R7MissionBindingError(RuntimeError):
    pass


@dataclass(frozen=True)
class R7RunResult:
    mission_id: str
    mission_status: str
    phase: str
    waiting_task_id: str | None = None
    emergency_restore_receipt_id: str | None = None


def _stable_plan_id(mission_id: str, task_id: str, call: ToolCall) -> str:
    payload = json.dumps(
        {
            "mission_id": mission_id,
            "task_id": task_id,
            "action": call.action,
            "params": dict(call.params),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "a200-r7-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


class A200SupervisedMissionExecutor:
    """Execution adapter owned by A200; MissionEngine remains state/DAG authority."""

    def __init__(
        self,
        *,
        mission_engine: MissionEngine,
        read_binding: A200ReadOnlyPcExecutionBinding,
        mutation_binding: A200ReversibleMutationBinding,
    ) -> None:
        self.engine = mission_engine
        self.read_binding = read_binding
        self.mutation_binding = mutation_binding

        self._active_mission_id: str | None = None
        self._active_task_id: str | None = None
        self._confirmed_for_active_call = False

        self._recovery_token: A200RecoveryToken | None = None
        self._mutation_task_id: str | None = None
        self._mutation_receipt_id: str | None = None
        self._r2_mutation_plan_digest: str | None = None
        self.last_emergency_restore_receipt_id: str | None = None

    @property
    def recovery_pending(self) -> bool:
        return self._recovery_token is not None

    def build_mission_task_specs(self, *, hwnd: int, title: str) -> list[dict[str, Any]]:
        hwnd = int(hwnd)
        title = str(title or "").strip()
        if hwnd <= 0 or not title:
            raise R7MissionBindingError("exact HWND/title target required")

        return [
            {
                "key": "observe_before",
                "title": "Read foreground window before mutation",
                "tool_name": "a200.r4.read",
                "action": "pc.get_foreground_window",
                "params": {},
                "max_attempts": 1,
            },
            {
                "key": "minimize_once",
                "title": "Minimize one exact supervised window",
                "tool_name": "a200.r5.reversible",
                "action": REVERSIBLE_ACTION,
                "params": {"hwnd": hwnd, "title": title},
                "depends_on": ["observe_before"],
                "max_attempts": 1,
            },
            {
                "key": "observe_mutated",
                "title": "Read foreground after reversible mutation",
                "tool_name": "a200.r4.read",
                "action": "pc.get_foreground_window",
                "params": {},
                "depends_on": ["minimize_once"],
                "max_attempts": 1,
            },
            {
                "key": "restore_exact",
                "title": "Restore exact W132 recovery preimage",
                "tool_name": "a200.r5.restore",
                "action": RESTORE_ACTION,
                "params": {},
                "depends_on": ["observe_mutated"],
                "max_attempts": 1,
            },
            {
                "key": "observe_final",
                "title": "Read foreground after exact restoration",
                "tool_name": "a200.r4.read",
                "action": "pc.get_foreground_window",
                "params": {},
                "depends_on": ["restore_exact"],
                "max_attempts": 1,
            },
        ]

    def tool_executor(self, call: ToolCall) -> dict[str, Any]:
        """MissionEngine injected tool executor. Synchronous and fail-closed."""
        mission_id = self._active_mission_id
        task_id = self._active_task_id
        if not mission_id or not task_id:
            raise R7MissionBindingError("MissionEngine task context is not armed")

        action = str(call.action or "")
        params = dict(call.params or {})

        if action in READ_ACTIONS:
            record = self.read_binding.execute_capability(
                action,
                params=params,
                step_id=task_id,
            )
            if not record.ok or record.status != "succeeded":
                raise R7MissionBindingError(
                    f"read action failed: {action} status={record.status} receipt={record.receipt_id}"
                )
            return {
                "kind": "a200_read",
                "action": action,
                "status": record.status,
                "ok": record.ok,
                "receipt_id": record.receipt_id,
                "evidence_refs": list(record.evidence_refs),
                "output": record.output,
            }

        if action == REVERSIBLE_ACTION:
            if not self._confirmed_for_active_call:
                raise R7MissionBindingError(
                    "reversible mutation reached executor without explicit MissionEngine confirmation"
                )

            r2_plan = SupervisedPlan.from_steps(
                goal="A200-R7 one exact reversible mutation inside canonical MissionEngine",
                plan_id=_stable_plan_id(mission_id, task_id, call),
                steps=[
                    {
                        "step_id": "mutate",
                        "capability_id": REVERSIBLE_ACTION,
                        "action": REVERSIBLE_ACTION,
                        "summary": "One exact supervised minimize",
                        "risk_tier": "REVERSIBLE",
                        "side_effect_class": "window_state",
                        "reversible": True,
                        "recovery_hint": "restore exact W132 preimage immediately or on failure",
                        "params_schema": params,
                    }
                ],
            )
            approval = ApprovalGrant.explicit_for(
                r2_plan,
                approval_scope=["mutate"],
            )
            result = self.mutation_binding.execute_one_reversible(
                r2_plan,
                approval=approval,
            )
            if not result.ok or result.status != "succeeded" or result.recovery_token is None:
                raise R7MissionBindingError(
                    f"reversible mutation failed status={result.status}"
                )

            self._recovery_token = result.recovery_token
            self._mutation_task_id = task_id
            self._mutation_receipt_id = result.receipt_id
            self._r2_mutation_plan_digest = r2_plan.digest()

            return {
                "kind": "a200_reversible_mutation",
                "action": action,
                "status": result.status,
                "ok": result.ok,
                "receipt_id": result.receipt_id,
                "r2_plan_id": r2_plan.plan_id,
                "r2_plan_digest": r2_plan.digest(),
                "recovery_token_id": result.recovery_token.token_id,
            }

        if action == RESTORE_ACTION:
            token = self._recovery_token
            if token is None:
                raise R7MissionBindingError("planned restore has no pending recovery token")
            result = self.mutation_binding.restore(token)
            if not result.ok or result.status != "succeeded":
                raise R7MissionBindingError(
                    f"planned restore failed status={result.status}"
                )
            self._recovery_token = None
            return {
                "kind": "a200_exact_restore",
                "action": action,
                "status": result.status,
                "ok": result.ok,
                "receipt_id": result.receipt_id,
                "recovery_token_id": token.token_id,
            }

        raise R7MissionBindingError(f"action outside A200-R7 scope: {action!r}")

    def _execute_task(
        self,
        mission_id: str,
        task_id: str,
        *,
        user_confirmed: bool,
    ) -> Task:
        if self._active_task_id is not None:
            raise R7MissionBindingError("nested MissionEngine task execution refused")

        self._active_mission_id = mission_id
        self._active_task_id = task_id
        self._confirmed_for_active_call = bool(user_confirmed)
        try:
            return self.engine.execute_task(
                mission_id,
                task_id,
                user_confirmed=bool(user_confirmed),
            )
        finally:
            self._confirmed_for_active_call = False
            self._active_task_id = None
            self._active_mission_id = None

    def confirm_waiting_task(self, mission_id: str) -> Task:
        mission = self.engine.get_mission(mission_id)
        waiting = [
            task for task in mission.tasks.values()
            if task.status == "waiting_confirmation"
        ]
        if len(waiting) != 1:
            raise R7MissionBindingError(
                f"expected exactly one waiting task, found {len(waiting)}"
            )
        return self._execute_task(
            mission_id,
            waiting[0].task_id,
            user_confirmed=True,
        )

    def _emergency_restore(self, mission_id: str, reason: str) -> str | None:
        token = self._recovery_token
        mutation_task_id = self._mutation_task_id
        if token is None:
            return None

        result = self.mutation_binding.restore(token)
        receipt_id = result.receipt_id
        self.last_emergency_restore_receipt_id = receipt_id

        if mutation_task_id:
            self.engine.record_evidence(
                mission_id,
                mutation_task_id,
                "emergency_recovery",
                {
                    "reason": str(reason),
                    "status": result.status,
                    "ok": result.ok,
                    "receipt_id": receipt_id,
                    "recovery_token_id": token.token_id,
                },
            )

        if not result.ok or result.status != "succeeded":
            raise R7MissionBindingError(
                f"FAIL-SAFE RESTORE FAILED status={result.status} receipt={receipt_id}"
            )

        self._recovery_token = None
        return receipt_id

    def run_until_pause_or_complete(
        self,
        mission_id: str,
        *,
        max_task_executions: int = 16,
    ) -> R7RunResult:
        executed = 0

        while executed < max_task_executions:
            mission = self.engine.get_mission(mission_id)

            waiting = [
                task for task in mission.tasks.values()
                if task.status == "waiting_confirmation"
            ]
            if waiting:
                return R7RunResult(
                    mission_id=mission_id,
                    mission_status=mission.status,
                    phase="waiting_confirmation",
                    waiting_task_id=waiting[0].task_id,
                )

            if mission.status in {"completed", "cancelled", "failed"}:
                return R7RunResult(
                    mission_id=mission_id,
                    mission_status=mission.status,
                    phase=mission.status,
                    emergency_restore_receipt_id=self.last_emergency_restore_receipt_id,
                )

            if mission.tasks and all(
                task.status == "succeeded" for task in mission.tasks.values()
            ):
                completed = self.engine.complete(mission_id)
                return R7RunResult(
                    mission_id=mission_id,
                    mission_status=completed.status,
                    phase="completed",
                )

            ready = self.engine.next_ready_tasks(mission_id)
            if not ready:
                # If a task failed, perform fail-safe recovery outside the
                # now-blocked dependency chain and stop the mission.
                failed = [
                    task for task in self.engine.get_mission(mission_id).tasks.values()
                    if task.status == "failed"
                ]
                if failed:
                    receipt = self._emergency_restore(
                        mission_id,
                        "mission task failed: " + failed[0].key,
                    )
                    cancelled = self.engine.cancel(mission_id)
                    return R7RunResult(
                        mission_id=mission_id,
                        mission_status=cancelled.status,
                        phase="failed_recovered" if receipt else "failed",
                        emergency_restore_receipt_id=receipt,
                    )
                raise R7MissionBindingError(
                    "mission has no ready/waiting/failed task and is not complete"
                )

            for task in ready:
                current = self._execute_task(
                    mission_id,
                    task.task_id,
                    user_confirmed=False,
                )
                executed += 1

                if current.status == "waiting_confirmation":
                    return R7RunResult(
                        mission_id=mission_id,
                        mission_status=self.engine.get_mission(mission_id).status,
                        phase="waiting_confirmation",
                        waiting_task_id=current.task_id,
                    )

                if current.status == "failed":
                    receipt = self._emergency_restore(
                        mission_id,
                        "mission task failed: " + current.key,
                    )
                    cancelled = self.engine.cancel(mission_id)
                    return R7RunResult(
                        mission_id=mission_id,
                        mission_status=cancelled.status,
                        phase="failed_recovered" if receipt else "failed",
                        emergency_restore_receipt_id=receipt,
                    )

        if self._recovery_token is not None:
            receipt = self._emergency_restore(
                mission_id,
                "execution bound exceeded",
            )
            self.engine.cancel(mission_id)
            return R7RunResult(
                mission_id=mission_id,
                mission_status="cancelled",
                phase="bound_exceeded_recovered",
                emergency_restore_receipt_id=receipt,
            )

        raise R7MissionBindingError("maximum task execution bound exceeded")


def assert_r7_safety_contract() -> None:
    if AUTONOMOUS_MULTI_MUTATION_ENABLED:
        raise RuntimeError("multi-mutation must stay disabled")
    if AUTONOMOUS_RETRY_ENABLED:
        raise RuntimeError("autonomous retry must stay disabled")
    if DESTRUCTIVE_EXECUTION_ENABLED:
        raise RuntimeError("destructive execution must stay disabled")
    if not FAIL_SAFE_RECOVERY_REQUIRED:
        raise RuntimeError("fail-safe recovery must be mandatory")
