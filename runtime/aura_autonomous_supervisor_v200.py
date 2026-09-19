"""AURA A200-R2 supervised autonomous task-plan contract.

This module is intentionally PRE-EXECUTION ONLY.

Canonical authorities remain:
- mission_engine.engine.MissionEngine: mission/task graph, task state, evidence, recovery.
- security.policy_engine.SecurityPolicyEngine: authorization authority.
- action_receipts.service.ActionReceiptService: action traceability authority.
- integrations.registry.IntegrationRegistry: provider/capability execution authority.

A200-R2 adds no second executor, no shell bridge and no autonomous PC mutation.
It validates a proposed multi-step plan, derives supervision requirements and can
produce an execution envelope for a later A200 gate. execute() is deliberately
absent.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Sequence


A200_R2_MARKER = "AURA_A200_R2_SUPERVISED_TASK_PLAN_CONTRACT_V1"
EXECUTION_ENABLED = False

CANONICAL_AUTHORITIES = {
    "mission": "mission_engine.engine.MissionEngine",
    "policy": "security.policy_engine.SecurityPolicyEngine",
    "receipt": "action_receipts.service.ActionReceiptService",
    "registry": "integrations.registry.IntegrationRegistry",
}

DENIED_ACTION_PATTERNS = (
    r"(?i)\bclose[_ -]?window\b",
    r"(?i)\bterminate[_ -]?process\b",
    r"(?i)\bkill[_ -]?process\b",
    r"(?i)\bshutdown\b",
    r"(?i)\breboot\b",
    r"(?i)\bformat\b",
    r"(?i)\bdelete[_ -]?(?:file|folder|directory)\b",
    r"(?i)\b(?:powershell|cmd(?:\.exe)?|bash|sh)\b",
    r"(?i)\b(?:subprocess|os\.system|os\.popen)\b",
)


class PlanContractError(ValueError):
    pass


class PlanBlockedError(PlanContractError):
    pass


class ApprovalError(PlanContractError):
    pass


class RiskTier(str, Enum):
    READ_ONLY = "READ_ONLY"
    REVERSIBLE = "REVERSIBLE"
    MUTATING = "MUTATING"
    DESTRUCTIVE = "DESTRUCTIVE"


class PolicyIntent(str, Enum):
    ALLOW = "ALLOW"
    REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"
    DENY = "DENY"


@dataclass(frozen=True)
class StepSpec:
    step_id: str
    capability_id: str
    action: str
    summary: str
    depends_on: tuple[str, ...] = ()
    risk_tier: RiskTier = RiskTier.READ_ONLY
    side_effect_class: str = "read_only"
    requires_confirmation: bool = False
    evidence_required: bool = True
    reversible: bool = False
    recovery_hint: str | None = None
    params_schema: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "StepSpec":
        try:
            tier = raw.get("risk_tier", RiskTier.READ_ONLY)
            if not isinstance(tier, RiskTier):
                tier = RiskTier(str(tier).upper())
        except Exception as exc:
            raise PlanContractError(f"unknown risk_tier for step {raw.get('step_id')!r}") from exc

        deps = raw.get("depends_on", ())
        if deps is None:
            deps = ()
        if isinstance(deps, str):
            deps = (deps,)
        return cls(
            step_id=str(raw.get("step_id", "")).strip(),
            capability_id=str(raw.get("capability_id", "")).strip(),
            action=str(raw.get("action", "")).strip(),
            summary=str(raw.get("summary", "")).strip(),
            depends_on=tuple(str(x).strip() for x in deps if str(x).strip()),
            risk_tier=tier,
            side_effect_class=str(raw.get("side_effect_class", "read_only")).strip() or "read_only",
            requires_confirmation=bool(raw.get("requires_confirmation", False)),
            evidence_required=bool(raw.get("evidence_required", True)),
            reversible=bool(raw.get("reversible", False)),
            recovery_hint=(
                str(raw.get("recovery_hint")).strip()
                if raw.get("recovery_hint") is not None
                else None
            ),
            params_schema=dict(raw.get("params_schema") or {}),
        )

    def canonical(self) -> dict[str, Any]:
        data = asdict(self)
        data["risk_tier"] = self.risk_tier.value
        data["depends_on"] = list(self.depends_on)
        data["params_schema"] = dict(self.params_schema)
        return data


@dataclass(frozen=True)
class ApprovalGrant:
    plan_id: str
    plan_digest: str
    approved_by: str
    approval_scope: tuple[str, ...]
    explicit: bool
    note: str = ""

    @classmethod
    def explicit_for(
        cls,
        plan: "SupervisedPlan",
        *,
        approved_by: str = "user",
        approval_scope: Iterable[str] | None = None,
        note: str = "",
    ) -> "ApprovalGrant":
        scope = tuple(approval_scope or [s.step_id for s in plan.steps])
        return cls(
            plan_id=plan.plan_id,
            plan_digest=plan.digest(),
            approved_by=str(approved_by or "user"),
            approval_scope=scope,
            explicit=True,
            note=str(note or ""),
        )


@dataclass(frozen=True)
class StepAssessment:
    step_id: str
    policy_intent: PolicyIntent
    reasons: tuple[str, ...]
    evidence_required: bool
    reversible: bool


@dataclass(frozen=True)
class SupervisionAssessment:
    plan_id: str
    plan_digest: str
    policy_intent: PolicyIntent
    requires_confirmation: bool
    blocked: bool
    step_assessments: tuple[StepAssessment, ...]
    topological_order: tuple[str, ...]
    execution_enabled: bool = EXECUTION_ENABLED

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "plan_digest": self.plan_digest,
            "policy_intent": self.policy_intent.value,
            "requires_confirmation": self.requires_confirmation,
            "blocked": self.blocked,
            "step_assessments": [
                {
                    "step_id": s.step_id,
                    "policy_intent": s.policy_intent.value,
                    "reasons": list(s.reasons),
                    "evidence_required": s.evidence_required,
                    "reversible": s.reversible,
                }
                for s in self.step_assessments
            ],
            "topological_order": list(self.topological_order),
            "execution_enabled": self.execution_enabled,
        }


@dataclass(frozen=True)
class SupervisedPlan:
    plan_id: str
    goal: str
    steps: tuple[StepSpec, ...]
    context_refs: tuple[str, ...] = ()
    max_retry_per_step: int = 1

    @classmethod
    def from_steps(
        cls,
        *,
        goal: str,
        steps: Sequence[Mapping[str, Any] | StepSpec],
        plan_id: str | None = None,
        context_refs: Sequence[str] = (),
        max_retry_per_step: int = 1,
    ) -> "SupervisedPlan":
        goal = str(goal or "").strip()
        if not goal:
            raise PlanContractError("goal is required")
        built = tuple(s if isinstance(s, StepSpec) else StepSpec.from_mapping(s) for s in steps)
        if not built:
            raise PlanContractError("at least one step is required")
        retry = int(max_retry_per_step)
        if retry < 0 or retry > 3:
            raise PlanContractError("max_retry_per_step must be between 0 and 3")
        if plan_id is None:
            seed = {
                "goal": goal,
                "steps": [s.canonical() for s in built],
                "context_refs": list(context_refs),
            }
            plan_id = "a200-" + hashlib.sha256(_canonical_json(seed).encode("utf-8")).hexdigest()[:16]
        return cls(
            plan_id=str(plan_id).strip(),
            goal=goal,
            steps=built,
            context_refs=tuple(str(x) for x in context_refs),
            max_retry_per_step=retry,
        )

    def canonical(self) -> dict[str, Any]:
        return {
            "schema": "aura.a200.supervised-plan.v1",
            "plan_id": self.plan_id,
            "goal": self.goal,
            "steps": [s.canonical() for s in self.steps],
            "context_refs": list(self.context_refs),
            "max_retry_per_step": self.max_retry_per_step,
        }

    def digest(self) -> str:
        return hashlib.sha256(_canonical_json(self.canonical()).encode("utf-8")).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _is_denied_action(step: StepSpec) -> bool:
    haystack = " ".join((step.action, step.capability_id, step.summary))
    return any(re.search(rx, haystack) for rx in DENIED_ACTION_PATTERNS)


def _validate_identifiers(plan: SupervisedPlan) -> dict[str, StepSpec]:
    seen: dict[str, StepSpec] = {}
    for step in plan.steps:
        if not step.step_id:
            raise PlanContractError("every step requires step_id")
        if step.step_id in seen:
            raise PlanContractError(f"duplicate step_id: {step.step_id}")
        if not step.capability_id:
            raise PlanContractError(f"{step.step_id}: capability_id is required")
        if not step.action:
            raise PlanContractError(f"{step.step_id}: action is required")
        if not step.summary:
            raise PlanContractError(f"{step.step_id}: summary is required")
        if step.step_id in step.depends_on:
            raise PlanContractError(f"{step.step_id}: self dependency is forbidden")
        seen[step.step_id] = step
    for step in plan.steps:
        missing = [d for d in step.depends_on if d not in seen]
        if missing:
            raise PlanContractError(f"{step.step_id}: missing dependencies {missing}")
    return seen


def topological_order(plan: SupervisedPlan) -> tuple[str, ...]:
    by_id = _validate_identifiers(plan)
    incoming = {sid: set(step.depends_on) for sid, step in by_id.items()}
    order: list[str] = []
    ready = sorted(sid for sid, deps in incoming.items() if not deps)

    while ready:
        sid = ready.pop(0)
        order.append(sid)
        for other in sorted(incoming):
            if sid in incoming[other]:
                incoming[other].remove(sid)
                if not incoming[other] and other not in order and other not in ready:
                    ready.append(other)
                    ready.sort()

    if len(order) != len(by_id):
        cycle_nodes = sorted(sid for sid, deps in incoming.items() if deps)
        raise PlanContractError(f"cycle detected in plan: {cycle_nodes}")
    return tuple(order)


def assess_step(step: StepSpec) -> StepAssessment:
    reasons: list[str] = []

    if _is_denied_action(step):
        reasons.append("action denied by A200-R2 hard safety pattern")
        return StepAssessment(
            step_id=step.step_id,
            policy_intent=PolicyIntent.DENY,
            reasons=tuple(reasons),
            evidence_required=True,
            reversible=step.reversible,
        )

    if step.risk_tier is RiskTier.DESTRUCTIVE:
        reasons.append("destructive actions are not eligible in A200-R2")
        return StepAssessment(
            step_id=step.step_id,
            policy_intent=PolicyIntent.DENY,
            reasons=tuple(reasons),
            evidence_required=True,
            reversible=step.reversible,
        )

    if step.risk_tier is RiskTier.READ_ONLY:
        if step.side_effect_class.lower() not in {"read_only", "none", "observation"}:
            reasons.append("read-only risk tier conflicts with declared side effect")
            return StepAssessment(
                step_id=step.step_id,
                policy_intent=PolicyIntent.DENY,
                reasons=tuple(reasons),
                evidence_required=True,
                reversible=step.reversible,
            )
        if step.requires_confirmation:
            reasons.append("step explicitly requests user confirmation")
            intent = PolicyIntent.REQUIRE_CONFIRMATION
        else:
            reasons.append("read-only observation may be prepared without confirmation")
            intent = PolicyIntent.ALLOW
        return StepAssessment(
            step_id=step.step_id,
            policy_intent=intent,
            reasons=tuple(reasons),
            evidence_required=step.evidence_required,
            reversible=step.reversible,
        )

    if step.risk_tier is RiskTier.REVERSIBLE:
        if not step.reversible:
            reasons.append("REVERSIBLE tier requires reversible=True")
            return StepAssessment(
                step_id=step.step_id,
                policy_intent=PolicyIntent.DENY,
                reasons=tuple(reasons),
                evidence_required=True,
                reversible=False,
            )
        if not step.recovery_hint:
            reasons.append("REVERSIBLE tier requires recovery_hint")
            return StepAssessment(
                step_id=step.step_id,
                policy_intent=PolicyIntent.DENY,
                reasons=tuple(reasons),
                evidence_required=True,
                reversible=True,
            )
        reasons.append("reversible side effect requires explicit confirmation")
        return StepAssessment(
            step_id=step.step_id,
            policy_intent=PolicyIntent.REQUIRE_CONFIRMATION,
            reasons=tuple(reasons),
            evidence_required=True,
            reversible=True,
        )

    if step.risk_tier is RiskTier.MUTATING:
        reasons.append("mutating side effect requires explicit confirmation")
        return StepAssessment(
            step_id=step.step_id,
            policy_intent=PolicyIntent.REQUIRE_CONFIRMATION,
            reasons=tuple(reasons),
            evidence_required=True,
            reversible=step.reversible,
        )

    reasons.append("unknown risk tier")
    return StepAssessment(
        step_id=step.step_id,
        policy_intent=PolicyIntent.DENY,
        reasons=tuple(reasons),
        evidence_required=True,
        reversible=step.reversible,
    )


def assess_plan(plan: SupervisedPlan) -> SupervisionAssessment:
    order = topological_order(plan)
    step_assessments = tuple(assess_step(s) for s in plan.steps)

    blocked = any(s.policy_intent is PolicyIntent.DENY for s in step_assessments)
    requires_confirmation = any(
        s.policy_intent is PolicyIntent.REQUIRE_CONFIRMATION for s in step_assessments
    )

    if blocked:
        intent = PolicyIntent.DENY
    elif requires_confirmation:
        intent = PolicyIntent.REQUIRE_CONFIRMATION
    else:
        intent = PolicyIntent.ALLOW

    return SupervisionAssessment(
        plan_id=plan.plan_id,
        plan_digest=plan.digest(),
        policy_intent=intent,
        requires_confirmation=requires_confirmation,
        blocked=blocked,
        step_assessments=step_assessments,
        topological_order=order,
    )


def validate_approval(
    plan: SupervisedPlan,
    assessment: SupervisionAssessment,
    approval: ApprovalGrant | None,
) -> bool:
    if assessment.blocked:
        raise ApprovalError("blocked plan cannot be approved")
    if not assessment.requires_confirmation:
        return True
    if approval is None:
        raise ApprovalError("explicit approval is required")
    if not approval.explicit:
        raise ApprovalError("approval must be explicit")
    if approval.plan_id != plan.plan_id:
        raise ApprovalError("approval plan_id mismatch")
    if approval.plan_digest != plan.digest():
        raise ApprovalError("approval is stale: plan digest mismatch")

    required_scope = {
        s.step_id
        for s in assessment.step_assessments
        if s.policy_intent is PolicyIntent.REQUIRE_CONFIRMATION
    }
    granted_scope = set(approval.approval_scope)
    missing = sorted(required_scope - granted_scope)
    if missing:
        raise ApprovalError(f"approval scope missing steps: {missing}")
    return True


def build_execution_envelope(
    plan: SupervisedPlan,
    *,
    approval: ApprovalGrant | None = None,
) -> dict[str, Any]:
    """Return a non-executing handoff envelope for a later A200 execution gate."""
    assessment = assess_plan(plan)
    if assessment.blocked:
        raise PlanBlockedError("plan contains denied step(s)")
    validate_approval(plan, assessment, approval)

    by_id = {s.step_id: s for s in plan.steps}
    tasks = []
    for sid in assessment.topological_order:
        step = by_id[sid]
        tasks.append(
            {
                "task_id": sid,
                "capability_id": step.capability_id,
                "action": step.action,
                "summary": step.summary,
                "depends_on": list(step.depends_on),
                "risk_tier": step.risk_tier.value,
                "requires_confirmation": (
                    assess_step(step).policy_intent
                    is PolicyIntent.REQUIRE_CONFIRMATION
                ),
                "evidence_required": step.evidence_required,
                "reversible": step.reversible,
                "recovery_hint": step.recovery_hint,
                "params_schema": dict(step.params_schema),
            }
        )

    return {
        "schema": "aura.a200.execution-envelope.v1",
        "a200_marker": A200_R2_MARKER,
        "plan_id": plan.plan_id,
        "plan_digest": plan.digest(),
        "goal": plan.goal,
        "canonical_authorities": dict(CANONICAL_AUTHORITIES),
        "policy_intent": assessment.policy_intent.value,
        "approval_bound": bool(approval and approval.explicit),
        "approval_scope": list(approval.approval_scope) if approval else [],
        "execution_enabled": False,
        "execution_gate": "A200-R3_OR_LATER",
        "max_retry_per_step": plan.max_retry_per_step,
        "context_refs": list(plan.context_refs),
        "tasks": tasks,
    }


def assert_execution_disabled() -> None:
    """Fail closed if anything tries to treat R2 as an executor."""
    raise RuntimeError(
        "A200-R2 is PRE-EXECUTION ONLY; autonomous execution is disabled until a later certified gate."
    )
