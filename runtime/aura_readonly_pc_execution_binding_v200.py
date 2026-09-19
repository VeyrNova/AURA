"""AURA A200-R4 read-only execution binding.

First real A200 execution gate.

Only three already-certified W131 read capabilities may cross this adapter:
- pc.discover_windows
- pc.discover_processes
- pc.get_foreground_window

All other capabilities are rejected before IntegrationRequest creation.

The actual call path deliberately remains canonical:
A200 R2 plan -> A200 R3 handoff -> this read-only guard ->
IntegrationRequest -> IntegrationRegistry.execute_integration ->
existing W131 PcControlWindowsProvider -> ActionReceiptService.

No new PC backend is introduced.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from integrations.registry import IntegrationRegistry, IntegrationRequest
from integrations.pc_control import PC_CONTROL_PROVIDER_ID
from runtime.aura_pc_control_registry_binding_v131 import register_pc_control_provider_v131
from runtime.aura_autonomous_supervisor_v200 import (
    PolicyIntent,
    RiskTier,
    SupervisedPlan,
    assess_plan,
    assess_step,
)
from runtime.aura_mission_supervision_adapter_v200 import (
    A200MissionSupervisionAdapter,
)


A200_R4_MARKER = "AURA_A200_R4_READ_ONLY_EXECUTION_BINDING_V1"

READ_ONLY_CAPABILITIES = frozenset({
    "pc.discover_windows",
    "pc.discover_processes",
    "pc.get_foreground_window",
})

EXPLICITLY_NON_READ_ONLY_CAPABILITIES = frozenset({
    "pc.focus_window",
    "pc.minimize_window",
    "pc.maximize_window",
    "pc.restore_window_state",
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

AUTONOMOUS_MUTATION_ENABLED = False
READ_ONLY_EXECUTION_ENABLED = True


class ReadOnlyExecutionDenied(PermissionError):
    pass


@dataclass(frozen=True)
class ReadOnlyExecutionRecord:
    step_id: str
    capability_id: str
    status: str
    ok: bool
    receipt_id: str | None
    evidence_refs: tuple[str, ...]
    output: Any

    def summary(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "capability_id": self.capability_id,
            "status": self.status,
            "ok": self.ok,
            "receipt_id": self.receipt_id,
            "evidence_ref_count": len(self.evidence_refs),
            "output_type": type(self.output).__name__,
        }


class A200ReadOnlyPcExecutionBinding:
    """Strict A200 gate around the existing W131 IntegrationRegistry path."""

    def __init__(
        self,
        *,
        registry: IntegrationRegistry,
        origin: str = "a200-r4-read-only",
    ) -> None:
        self.registry = registry
        self.origin = str(origin or "a200-r4-read-only")

    @classmethod
    def create_with_existing_w131_provider(
        cls,
        *,
        receipt_service: Any,
        security_engine: Any,
        backend: Any = None,
        origin: str = "a200-r4-read-only",
    ) -> "A200ReadOnlyPcExecutionBinding":
        registry = IntegrationRegistry(
            security_engine=security_engine,
            receipt_service=receipt_service,
        )
        register_pc_control_provider_v131(registry, backend=backend)
        return cls(registry=registry, origin=origin)

    @staticmethod
    def _validate_raw_params(params: Mapping[str, Any] | None) -> dict[str, Any]:
        safe = dict(params or {})
        bad = sorted(
            str(key)
            for key in safe
            if str(key).strip().casefold() in RAW_EXECUTION_KEYS
        )
        if bad:
            raise ReadOnlyExecutionDenied(
                f"raw execution material denied by A200-R4: {bad}"
            )
        return safe

    @staticmethod
    def _validate_capability(capability_id: str) -> str:
        cap = str(capability_id or "").strip()
        if cap not in READ_ONLY_CAPABILITIES:
            raise ReadOnlyExecutionDenied(
                f"A200-R4 capability is not read-only allowlisted: {cap!r}"
            )
        return cap

    def execute_capability(
        self,
        capability_id: str,
        *,
        params: Mapping[str, Any] | None = None,
        step_id: str = "direct-read",
    ) -> ReadOnlyExecutionRecord:
        cap = self._validate_capability(capability_id)
        safe_params = self._validate_raw_params(params)

        request = IntegrationRequest.create(
            provider_id=PC_CONTROL_PROVIDER_ID,
            capability_id=cap,
            params=safe_params,
            origin=self.origin,
        )
        result = self.registry.execute_integration(request)

        return ReadOnlyExecutionRecord(
            step_id=str(step_id),
            capability_id=cap,
            status=str(result.status),
            ok=bool(result.ok),
            receipt_id=result.receipt_id,
            evidence_refs=tuple(result.evidence_refs or ()),
            output=result.output,
        )

    def execute_plan(self, plan: SupervisedPlan) -> dict[str, Any]:
        assessment = assess_plan(plan)

        if assessment.blocked:
            raise ReadOnlyExecutionDenied("blocked A200 plan cannot execute in R4")
        if assessment.requires_confirmation:
            raise ReadOnlyExecutionDenied(
                "R4 executes read-only plans only; confirmation/mutation plan refused"
            )

        # Revalidate every step independently. Never trust caller risk labels alone.
        by_id = {s.step_id: s for s in plan.steps}
        for step in plan.steps:
            if step.risk_tier is not RiskTier.READ_ONLY:
                raise ReadOnlyExecutionDenied(
                    f"{step.step_id}: non-read-only risk tier refused"
                )
            step_assessment = assess_step(step)
            if step_assessment.policy_intent is not PolicyIntent.ALLOW:
                raise ReadOnlyExecutionDenied(
                    f"{step.step_id}: policy preflight is not ALLOW"
                )
            self._validate_capability(step.capability_id)
            self._validate_raw_params(step.params_schema)

        # Require the R3 canonical handoff to remain execution-disabled. R4 is
        # the only component in this chain allowed to cross into real read calls.
        handoff = A200MissionSupervisionAdapter().prepare_handoff(plan)
        if handoff.execution_enabled:
            raise ReadOnlyExecutionDenied("R3 handoff unexpectedly executable")

        records: list[ReadOnlyExecutionRecord] = []
        completed: set[str] = set()

        for step_id in assessment.topological_order:
            step = by_id[step_id]
            if not set(step.depends_on).issubset(completed):
                raise ReadOnlyExecutionDenied(
                    f"{step_id}: dependency not completed"
                )
            record = self.execute_capability(
                step.capability_id,
                params=step.params_schema,
                step_id=step.step_id,
            )
            records.append(record)
            if not record.ok or record.status != "succeeded":
                return {
                    "schema": "aura.a200.r4.read-only-execution.v1",
                    "a200_r4_marker": A200_R4_MARKER,
                    "plan_id": plan.plan_id,
                    "plan_digest": plan.digest(),
                    "status": "failed",
                    "read_only_execution_enabled": True,
                    "autonomous_mutation_enabled": False,
                    "records": [r.summary() for r in records],
                }
            completed.add(step_id)

        return {
            "schema": "aura.a200.r4.read-only-execution.v1",
            "a200_r4_marker": A200_R4_MARKER,
            "plan_id": plan.plan_id,
            "plan_digest": plan.digest(),
            "status": "succeeded",
            "read_only_execution_enabled": True,
            "autonomous_mutation_enabled": False,
            "records": [r.summary() for r in records],
        }


def assert_mutation_disabled() -> None:
    raise RuntimeError(
        "A200-R4 permits only certified read-only PC discovery; mutation remains disabled."
    )
