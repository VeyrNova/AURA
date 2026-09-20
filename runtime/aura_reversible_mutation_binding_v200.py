"""AURA A200-R5 reversible mutation approval + recovery binding.

A200-R5 enables ONE explicitly-approved reversible Windows mutation at a time:
- pc.focus_window
- pc.minimize_window
- pc.maximize_window

The plan approval is bound to the exact A200-R2 plan digest.
The existing W132 recovery preimage returned by the certified PC provider is
captured and wrapped in a one-use A200 recovery token.

Destructive actions remain denied. Raw shell material remains denied.
This module does not introduce a new PC backend or shell path.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from integrations.registry import IntegrationRegistry, IntegrationRequest
from integrations.pc_control import PC_CONTROL_PROVIDER_ID
from runtime.aura_autonomous_supervisor_v200 import (
    ApprovalGrant,
    PolicyIntent,
    RiskTier,
    SupervisedPlan,
    assess_plan,
    assess_step,
    validate_approval,
)
from runtime.aura_mission_supervision_adapter_v200 import A200MissionSupervisionAdapter


A200_R5_MARKER = "AURA_A200_R5_REVERSIBLE_MUTATION_APPROVAL_RECOVERY_V1"

REVERSIBLE_MUTATION_CAPABILITIES = frozenset({
    "pc.focus_window",
    "pc.minimize_window",
    "pc.maximize_window",
})

RESTORE_CAPABILITY = "pc.restore_window_state"

PERMANENTLY_DENIED_CAPABILITIES = frozenset({
    "pc.close_window",
    "pc.terminate_process",
})

RAW_EXECUTION_KEYS = frozenset({
    "command",
    "cmd",
    "shell",
    "powershell",
    "script",
    "argv",
    "arguments",
    "executable",
    "exe_path",
})

AUTONOMOUS_MULTI_MUTATION_ENABLED = False
DESTRUCTIVE_EXECUTION_ENABLED = False
REVERSIBLE_ONE_STEP_EXECUTION_ENABLED = True


class ReversibleMutationDenied(PermissionError):
    pass


class RecoveryTokenError(RuntimeError):
    pass


@dataclass(frozen=True)
class A200RecoveryToken:
    token_id: str
    plan_id: str
    plan_digest: str
    step_id: str
    mutation_capability: str
    mutation_receipt_id: str
    recovery_digest: str


@dataclass(frozen=True)
class A200MutationResult:
    status: str
    ok: bool
    plan_id: str
    plan_digest: str
    step_id: str
    capability_id: str
    receipt_id: str | None
    recovery_token: A200RecoveryToken | None
    output: Any


@dataclass(frozen=True)
class A200RestoreResult:
    status: str
    ok: bool
    recovery_token_id: str
    receipt_id: str | None
    output: Any


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class A200ReversibleMutationBinding:
    """One-step mutation gate over the already-certified IntegrationRegistry."""

    def __init__(self, *, registry: IntegrationRegistry, origin: str = "a200-r5") -> None:
        self.registry = registry
        self.origin = str(origin or "a200-r5")
        self._recoveries: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _reject_raw_execution_material(params: Mapping[str, Any]) -> None:
        bad = sorted(
            str(k) for k in params
            if str(k).strip().casefold() in RAW_EXECUTION_KEYS
        )
        if bad:
            raise ReversibleMutationDenied(
                f"raw execution material denied by A200-R5: {bad}"
            )

    @staticmethod
    def _validate_exact_target(params: Mapping[str, Any]) -> dict[str, Any]:
        safe = dict(params or {})
        A200ReversibleMutationBinding._reject_raw_execution_material(safe)

        try:
            hwnd = int(safe.get("hwnd"))
        except Exception as exc:
            raise ReversibleMutationDenied("exact positive HWND is required") from exc
        title = str(safe.get("title") or "").strip()

        if hwnd <= 0:
            raise ReversibleMutationDenied("exact positive HWND is required")
        if not title:
            raise ReversibleMutationDenied("exact non-empty window title is required")

        # R5 intentionally accepts only the minimum target identity.
        extra = sorted(set(safe) - {"hwnd", "title"})
        if extra:
            raise ReversibleMutationDenied(
                f"unexpected mutation params refused in R5: {extra}"
            )
        return {"hwnd": hwnd, "title": title}

    @staticmethod
    def _extract_recovery(output: Any) -> dict[str, Any]:
        if not isinstance(output, Mapping):
            raise RecoveryTokenError("provider output is not a mapping")
        pc_result = output.get("pc_result")
        if not isinstance(pc_result, Mapping):
            raise RecoveryTokenError("provider output has no pc_result")
        data = pc_result.get("data")
        if not isinstance(data, Mapping):
            raise RecoveryTokenError("pc_result has no data")
        recovery = data.get("recovery")
        if not isinstance(recovery, Mapping):
            raise RecoveryTokenError("certified W132 recovery preimage missing")

        recovery = dict(recovery)
        target = recovery.get("target")
        if not isinstance(target, Mapping):
            raise RecoveryTokenError("recovery target missing")
        if int(target.get("hwnd") or 0) <= 0:
            raise RecoveryTokenError("recovery target HWND invalid")
        if not str(target.get("title") or "").strip():
            raise RecoveryTokenError("recovery target title invalid")
        if str(target.get("show_state") or "") not in {"normal", "minimized", "maximized"}:
            raise RecoveryTokenError("recovery show_state invalid")
        if recovery.get("available") is not True:
            raise RecoveryTokenError("recovery descriptor not available")
        return recovery

    def _build_recovery_token(
        self,
        *,
        plan: SupervisedPlan,
        step_id: str,
        capability_id: str,
        mutation_receipt_id: str,
        recovery: Mapping[str, Any],
    ) -> A200RecoveryToken:
        recovery_copy = dict(recovery)
        recovery_digest = _digest(recovery_copy)
        token_seed = {
            "plan_id": plan.plan_id,
            "plan_digest": plan.digest(),
            "step_id": step_id,
            "capability_id": capability_id,
            "mutation_receipt_id": mutation_receipt_id,
            "recovery_digest": recovery_digest,
        }
        token_id = "a200-recovery-" + _digest(token_seed)[:24]
        self._recoveries[token_id] = {
            "used": False,
            "recovery": recovery_copy,
            "recovery_digest": recovery_digest,
            "plan_digest": plan.digest(),
            "mutation_receipt_id": mutation_receipt_id,
        }
        return A200RecoveryToken(
            token_id=token_id,
            plan_id=plan.plan_id,
            plan_digest=plan.digest(),
            step_id=step_id,
            mutation_capability=capability_id,
            mutation_receipt_id=mutation_receipt_id,
            recovery_digest=recovery_digest,
        )

    def execute_one_reversible(
        self,
        plan: SupervisedPlan,
        *,
        approval: ApprovalGrant,
    ) -> A200MutationResult:
        assessment = assess_plan(plan)
        if assessment.blocked:
            raise ReversibleMutationDenied("blocked plan cannot execute")
        if not assessment.requires_confirmation:
            raise ReversibleMutationDenied(
                "R5 mutation must be classified REQUIRE_CONFIRMATION"
            )

        validate_approval(plan, assessment, approval)

        if len(plan.steps) != 1:
            raise ReversibleMutationDenied(
                "A200-R5 permits exactly one mutation step per approved plan"
            )

        step = plan.steps[0]
        if step.capability_id in PERMANENTLY_DENIED_CAPABILITIES:
            raise ReversibleMutationDenied("destructive capability permanently denied")
        if step.capability_id not in REVERSIBLE_MUTATION_CAPABILITIES:
            raise ReversibleMutationDenied(
                f"capability is not R5 reversible allowlisted: {step.capability_id}"
            )
        if step.risk_tier is not RiskTier.REVERSIBLE:
            raise ReversibleMutationDenied("R5 requires REVERSIBLE risk tier")
        if not step.reversible or not step.recovery_hint:
            raise ReversibleMutationDenied(
                "R5 requires reversible=True and explicit recovery_hint"
            )
        if assess_step(step).policy_intent is not PolicyIntent.REQUIRE_CONFIRMATION:
            raise ReversibleMutationDenied(
                "R5 step must require explicit confirmation"
            )

        safe_params = self._validate_exact_target(step.params_schema)

        # Reuse R3 handoff to prove the approval is bound to this exact plan.
        handoff = A200MissionSupervisionAdapter().prepare_handoff(
            plan,
            approval=approval,
        )
        if not handoff.approval_bound:
            raise ReversibleMutationDenied("R3 handoff did not bind approval")
        if handoff.plan_digest != plan.digest():
            raise ReversibleMutationDenied("R3 handoff digest mismatch")

        request = IntegrationRequest.create(
            provider_id=PC_CONTROL_PROVIDER_ID,
            capability_id=step.capability_id,
            params=safe_params,
            origin=self.origin,
        )
        result = self.registry.execute_integration(request)

        if not result.ok or str(result.status) != "succeeded":
            return A200MutationResult(
                status=str(result.status),
                ok=bool(result.ok),
                plan_id=plan.plan_id,
                plan_digest=plan.digest(),
                step_id=step.step_id,
                capability_id=step.capability_id,
                receipt_id=result.receipt_id,
                recovery_token=None,
                output=result.output,
            )

        if not result.receipt_id:
            raise RecoveryTokenError("successful mutation has no canonical receipt id")

        recovery = self._extract_recovery(result.output)
        token = self._build_recovery_token(
            plan=plan,
            step_id=step.step_id,
            capability_id=step.capability_id,
            mutation_receipt_id=result.receipt_id,
            recovery=recovery,
        )

        return A200MutationResult(
            status=str(result.status),
            ok=bool(result.ok),
            plan_id=plan.plan_id,
            plan_digest=plan.digest(),
            step_id=step.step_id,
            capability_id=step.capability_id,
            receipt_id=result.receipt_id,
            recovery_token=token,
            output=result.output,
        )

    def restore(self, token: A200RecoveryToken) -> A200RestoreResult:
        state = self._recoveries.get(token.token_id)
        if not isinstance(state, dict):
            raise RecoveryTokenError("unknown recovery token")
        if state.get("used") is True:
            raise RecoveryTokenError("recovery token already consumed")
        if state.get("recovery_digest") != token.recovery_digest:
            raise RecoveryTokenError("recovery token digest mismatch")
        if state.get("plan_digest") != token.plan_digest:
            raise RecoveryTokenError("recovery token plan digest mismatch")
        if state.get("mutation_receipt_id") != token.mutation_receipt_id:
            raise RecoveryTokenError("recovery token receipt mismatch")

        recovery = dict(state["recovery"])
        if _digest(recovery) != token.recovery_digest:
            raise RecoveryTokenError("stored recovery preimage changed")

        request = IntegrationRequest.create(
            provider_id=PC_CONTROL_PROVIDER_ID,
            capability_id=RESTORE_CAPABILITY,
            params=recovery,
            origin=self.origin + "-restore",
        )
        result = self.registry.execute_integration(request)

        if result.ok and str(result.status) == "succeeded":
            state["used"] = True

        return A200RestoreResult(
            status=str(result.status),
            ok=bool(result.ok),
            recovery_token_id=token.token_id,
            receipt_id=result.receipt_id,
            output=result.output,
        )

    def recovery_available(self, token: A200RecoveryToken) -> bool:
        state = self._recoveries.get(token.token_id)
        return bool(isinstance(state, dict) and not state.get("used"))


def assert_destructive_execution_disabled() -> None:
    raise RuntimeError(
        "A200-R5 allows one approved reversible window-state mutation only; destructive execution is disabled."
    )
