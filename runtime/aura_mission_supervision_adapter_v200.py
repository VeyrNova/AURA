"""AURA A200-R3 MissionEngine supervision adapter + dry-run simulation.

PRE-EXECUTION ONLY.

This module maps the A200-R2 supervised plan contract to a MissionEngine-oriented
handoff blueprint and simulates task-state transitions in memory.

It deliberately does NOT:
- instantiate IntegrationRegistry providers;
- call IntegrationRegistry.execute_integration;
- call MissionEngine.execute_task;
- create canonical ActionReceipts;
- invoke PC/window actions;
- invoke a shell/process.

Canonical execution authorities remain unchanged and are referenced in every
handoff for the later certified execution gate.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import inspect
import json
from typing import Any

from runtime.aura_autonomous_supervisor_v200 import (
    A200_R2_MARKER,
    ApprovalGrant,
    PlanBlockedError,
    PolicyIntent,
    SupervisedPlan,
    assess_plan,
    assess_step,
    validate_approval,
    CANONICAL_AUTHORITIES,
)


A200_R3_MARKER = "AURA_A200_R3_MISSION_SUPERVISION_DRY_RUN_V1"
DRY_RUN_ONLY = True
AUTONOMOUS_EXECUTION_ENABLED = False
CANONICAL_RECEIPTS_WRITTEN = False

MISSION_ENGINE_REQUIRED_METHODS = (
    "create_mission",
    "plan_mission",
    "start_mission",
    "next_ready_tasks",
    "execute_task",
    "record_evidence",
    "retry_task",
    "replan",
    "resume",
    "cancel",
    "complete",
    "get_mission",
)


class SimulationState(str, Enum):
    PLANNED = "planned"
    READY = "ready"
    WAITING_CONFIRMATION = "waiting_confirmation"
    SIMULATED_SUCCEEDED = "simulated_succeeded"
    BLOCKED_DEPENDENCY = "blocked_dependency"
    DENIED = "denied"


@dataclass(frozen=True)
class SimulationTrace:
    sequence: int
    plan_id: str
    step_id: str
    from_state: str
    to_state: str
    policy_intent: str
    evidence_ref: str
    receipt_mode: str = "SIMULATED_ONLY"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MissionHandoff:
    schema: str
    plan_id: str
    plan_digest: str
    goal: str
    status: str
    approval_required: bool
    approval_bound: bool
    execution_enabled: bool
    canonical_authorities: dict[str, str]
    required_mission_methods: tuple[str, ...]
    mission_payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["required_mission_methods"] = list(self.required_mission_methods)
        return value


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _evidence_ref(plan_digest: str, step_id: str, state: str) -> str:
    seed = f"{plan_digest}:{step_id}:{state}"
    return "sim-evidence-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]


def inspect_mission_engine_contract() -> dict[str, str]:
    """Read-only reflection of the canonical MissionEngine class."""
    from mission_engine.engine import MissionEngine

    missing = [
        name for name in MISSION_ENGINE_REQUIRED_METHODS
        if not callable(getattr(MissionEngine, name, None))
    ]
    if missing:
        raise RuntimeError(f"MissionEngine contract incomplete: {missing}")

    return {
        name: str(inspect.signature(getattr(MissionEngine, name)))
        for name in MISSION_ENGINE_REQUIRED_METHODS
    }


def _task_blueprints(plan: SupervisedPlan) -> list[dict[str, Any]]:
    assessment = assess_plan(plan)
    by_id = {step.step_id: step for step in plan.steps}
    rows: list[dict[str, Any]] = []

    for step_id in assessment.topological_order:
        step = by_id[step_id]
        step_assessment = assess_step(step)
        rows.append(
            {
                "task_id": step.step_id,
                "capability_id": step.capability_id,
                "action": step.action,
                "summary": step.summary,
                "depends_on": list(step.depends_on),
                "risk_tier": step.risk_tier.value,
                "policy_preflight_intent": step_assessment.policy_intent.value,
                "canonical_policy_recheck_required": True,
                "canonical_receipt_required_before_execution": True,
                "integration_registry_dispatch_required": True,
                "evidence_required": bool(step.evidence_required),
                "reversible": bool(step.reversible),
                "recovery_hint": step.recovery_hint,
                "params_schema": dict(step.params_schema),
            }
        )
    return rows


class A200MissionSupervisionAdapter:
    """MissionEngine-oriented A200 adapter with NO execution method."""

    def contract_snapshot(self) -> dict[str, Any]:
        return {
            "a200_r2_marker": A200_R2_MARKER,
            "a200_r3_marker": A200_R3_MARKER,
            "dry_run_only": DRY_RUN_ONLY,
            "autonomous_execution_enabled": AUTONOMOUS_EXECUTION_ENABLED,
            "canonical_receipts_written": CANONICAL_RECEIPTS_WRITTEN,
            "canonical_authorities": dict(CANONICAL_AUTHORITIES),
            "mission_engine_signatures": inspect_mission_engine_contract(),
        }

    def prepare_handoff(
        self,
        plan: SupervisedPlan,
        *,
        approval: ApprovalGrant | None = None,
    ) -> MissionHandoff:
        assessment = assess_plan(plan)
        if assessment.blocked:
            raise PlanBlockedError("A200-R3 refuses a plan containing denied step(s)")

        approval_bound = False
        if assessment.requires_confirmation:
            if approval is None:
                status = "waiting_confirmation"
            else:
                validate_approval(plan, assessment, approval)
                approval_bound = True
                status = "ready_for_later_execution_gate"
        else:
            if approval is not None:
                # An explicit approval may be carried, but it is not required for
                # a purely read-only plan.
                approval_bound = bool(approval.explicit and approval.plan_digest == plan.digest())
            status = "ready_for_later_execution_gate"

        payload = {
            "schema": "aura.a200.mission-handoff-blueprint.v1",
            "mission_engine_authority": CANONICAL_AUTHORITIES["mission"],
            "policy_authority": CANONICAL_AUTHORITIES["policy"],
            "receipt_authority": CANONICAL_AUTHORITIES["receipt"],
            "registry_authority": CANONICAL_AUTHORITIES["registry"],
            "goal": plan.goal,
            "plan_id": plan.plan_id,
            "plan_digest": plan.digest(),
            "context_refs": list(plan.context_refs),
            "max_retry_per_step": plan.max_retry_per_step,
            "tasks": _task_blueprints(plan),
            "execution_enabled": False,
            "handoff_gate": "A200-R4_OR_LATER",
        }

        return MissionHandoff(
            schema="aura.a200.mission-supervision-handoff.v1",
            plan_id=plan.plan_id,
            plan_digest=plan.digest(),
            goal=plan.goal,
            status=status,
            approval_required=assessment.requires_confirmation,
            approval_bound=approval_bound,
            execution_enabled=False,
            canonical_authorities=dict(CANONICAL_AUTHORITIES),
            required_mission_methods=MISSION_ENGINE_REQUIRED_METHODS,
            mission_payload=payload,
        )

    def simulate(
        self,
        plan: SupervisedPlan,
        *,
        approval: ApprovalGrant | None = None,
    ) -> dict[str, Any]:
        """Simulate dependency/approval transitions in memory, without tool calls."""
        handoff = self.prepare_handoff(plan, approval=approval)
        assessment = assess_plan(plan)
        by_id = {step.step_id: step for step in plan.steps}
        states = {step.step_id: SimulationState.PLANNED for step in plan.steps}
        traces: list[SimulationTrace] = []
        sequence = 0

        for step_id in assessment.topological_order:
            step = by_id[step_id]
            step_assessment = assess_step(step)

            deps_ok = all(
                states[dep] is SimulationState.SIMULATED_SUCCEEDED
                for dep in step.depends_on
            )
            if not deps_ok:
                old = states[step_id]
                states[step_id] = SimulationState.BLOCKED_DEPENDENCY
                sequence += 1
                traces.append(
                    SimulationTrace(
                        sequence=sequence,
                        plan_id=plan.plan_id,
                        step_id=step_id,
                        from_state=old.value,
                        to_state=SimulationState.BLOCKED_DEPENDENCY.value,
                        policy_intent=step_assessment.policy_intent.value,
                        evidence_ref=_evidence_ref(
                            plan.digest(), step_id, SimulationState.BLOCKED_DEPENDENCY.value
                        ),
                    )
                )
                continue

            old = states[step_id]
            states[step_id] = SimulationState.READY
            sequence += 1
            traces.append(
                SimulationTrace(
                    sequence=sequence,
                    plan_id=plan.plan_id,
                    step_id=step_id,
                    from_state=old.value,
                    to_state=SimulationState.READY.value,
                    policy_intent=step_assessment.policy_intent.value,
                    evidence_ref=_evidence_ref(
                        plan.digest(), step_id, SimulationState.READY.value
                    ),
                )
            )

            if step_assessment.policy_intent is PolicyIntent.DENY:
                old = states[step_id]
                states[step_id] = SimulationState.DENIED
                sequence += 1
                traces.append(
                    SimulationTrace(
                        sequence=sequence,
                        plan_id=plan.plan_id,
                        step_id=step_id,
                        from_state=old.value,
                        to_state=SimulationState.DENIED.value,
                        policy_intent=PolicyIntent.DENY.value,
                        evidence_ref=_evidence_ref(
                            plan.digest(), step_id, SimulationState.DENIED.value
                        ),
                    )
                )
                continue

            if (
                step_assessment.policy_intent is PolicyIntent.REQUIRE_CONFIRMATION
                and not handoff.approval_bound
            ):
                old = states[step_id]
                states[step_id] = SimulationState.WAITING_CONFIRMATION
                sequence += 1
                traces.append(
                    SimulationTrace(
                        sequence=sequence,
                        plan_id=plan.plan_id,
                        step_id=step_id,
                        from_state=old.value,
                        to_state=SimulationState.WAITING_CONFIRMATION.value,
                        policy_intent=PolicyIntent.REQUIRE_CONFIRMATION.value,
                        evidence_ref=_evidence_ref(
                            plan.digest(), step_id, SimulationState.WAITING_CONFIRMATION.value
                        ),
                    )
                )
                continue

            old = states[step_id]
            states[step_id] = SimulationState.SIMULATED_SUCCEEDED
            sequence += 1
            traces.append(
                SimulationTrace(
                    sequence=sequence,
                    plan_id=plan.plan_id,
                    step_id=step_id,
                    from_state=old.value,
                    to_state=SimulationState.SIMULATED_SUCCEEDED.value,
                    policy_intent=step_assessment.policy_intent.value,
                    evidence_ref=_evidence_ref(
                        plan.digest(), step_id, SimulationState.SIMULATED_SUCCEEDED.value
                    ),
                )
            )

        terminal = "simulated_complete"
        if any(v is SimulationState.WAITING_CONFIRMATION for v in states.values()):
            terminal = "waiting_confirmation"
        elif any(v is SimulationState.BLOCKED_DEPENDENCY for v in states.values()):
            terminal = "blocked_dependency"
        elif any(v is SimulationState.DENIED for v in states.values()):
            terminal = "denied"

        return {
            "schema": "aura.a200.mission-dry-run.v1",
            "a200_r3_marker": A200_R3_MARKER,
            "plan_id": plan.plan_id,
            "plan_digest": plan.digest(),
            "terminal_state": terminal,
            "execution_enabled": False,
            "pc_or_window_mutated": False,
            "canonical_receipts_written": False,
            "trace_mode": "SIMULATED_ONLY",
            "states": {k: v.value for k, v in states.items()},
            "traces": [t.to_dict() for t in traces],
            "handoff": handoff.to_dict(),
        }


def assert_execution_disabled() -> None:
    raise RuntimeError(
        "A200-R3 is DRY-RUN ONLY. Real MissionEngine/IntegrationRegistry execution is disabled."
    )
