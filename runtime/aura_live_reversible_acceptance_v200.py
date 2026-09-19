"""AURA A200-R6 controlled live reversible mutation acceptance.

This is an acceptance harness, not an autonomous desktop policy expansion.

Safety properties:
- caller must provide explicit human approval signal;
- only the harness's own console window may be targeted;
- target is resolved through canonical W131 read-only discovery;
- exactly one reversible action is allowed: pc.minimize_window;
- action uses A200-R5 exact plan-digest approval binding;
- W132 recovery preimage is mandatory;
- automatic restore is attempted immediately in a finally-safe flow;
- close/terminate/raw shell/multi-mutation remain unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from action_receipts import ActionReceiptService
from integrations.registry import IntegrationRegistry
from runtime.aura_autonomous_supervisor_v200 import ApprovalGrant, SupervisedPlan
from runtime.aura_pc_control_registry_binding_v131 import register_pc_control_provider_v131
from runtime.aura_readonly_pc_execution_binding_v200 import A200ReadOnlyPcExecutionBinding
from runtime.aura_reversible_mutation_binding_v200 import (
    A200ReversibleMutationBinding,
    A200MutationResult,
    A200RestoreResult,
)


A200_R6_MARKER = "AURA_A200_R6_CONTROLLED_LIVE_REVERSIBLE_ACCEPTANCE_V1"
SELF_WINDOW_MARKER = "AURA A200-R6 LIVE REVERSIBLE ACCEPTANCE"
LIVE_ACCEPTED_CAPABILITY = "pc.minimize_window"

AUTONOMOUS_MULTI_MUTATION_ENABLED = False
DESTRUCTIVE_EXECUTION_ENABLED = False
LIVE_SELF_WINDOW_ONLY = True
AUTO_RESTORE_REQUIRED = True


class LiveAcceptanceDenied(PermissionError):
    pass


@dataclass(frozen=True)
class LiveTarget:
    hwnd: int
    title: str


@dataclass(frozen=True)
class LiveAcceptanceResult:
    target: LiveTarget
    mutation: A200MutationResult
    restore: A200RestoreResult
    post_restore_visible: bool
    discovery_receipt_id: str | None
    verification_receipt_id: str | None


def _rows_from_read_output(output: Any) -> list[Mapping[str, Any]]:
    if not isinstance(output, Mapping):
        return []
    pc_result = output.get("pc_result")
    if not isinstance(pc_result, Mapping):
        return []
    data = pc_result.get("data")
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, Mapping)]


class A200ControlledLiveAcceptance:
    def __init__(
        self,
        *,
        registry: IntegrationRegistry,
        receipt_service: ActionReceiptService,
        origin: str = "a200-r6-live-acceptance",
    ) -> None:
        self.registry = registry
        self.receipt_service = receipt_service
        self.origin = str(origin or "a200-r6-live-acceptance")
        self.read_binding = A200ReadOnlyPcExecutionBinding(
            registry=registry,
            origin=self.origin + "-read",
        )
        self.mutation_binding = A200ReversibleMutationBinding(
            registry=registry,
            origin=self.origin + "-mutation",
        )

    @classmethod
    def create(
        cls,
        *,
        receipt_service: ActionReceiptService,
        security_engine: Any,
        backend: Any = None,
        origin: str = "a200-r6-live-acceptance",
    ) -> "A200ControlledLiveAcceptance":
        registry = IntegrationRegistry(
            security_engine=security_engine,
            receipt_service=receipt_service,
        )
        register_pc_control_provider_v131(registry, backend=backend)
        return cls(
            registry=registry,
            receipt_service=receipt_service,
            origin=origin,
        )

    def resolve_self_window(self) -> tuple[LiveTarget, str | None]:
        discovery = self.read_binding.execute_capability(
            "pc.discover_windows",
            params={},
            step_id="r6-resolve-self",
        )
        if not discovery.ok or discovery.status != "succeeded":
            raise LiveAcceptanceDenied("canonical Windows discovery failed")

        matches = []
        marker = SELF_WINDOW_MARKER.casefold()
        for row in _rows_from_read_output(discovery.output):
            title = str(row.get("title") or "").strip()
            try:
                hwnd = int(row.get("hwnd") or 0)
            except Exception:
                hwnd = 0
            if marker in title.casefold() and hwnd > 0:
                matches.append(LiveTarget(hwnd=hwnd, title=title))

        if len(matches) != 1:
            raise LiveAcceptanceDenied(
                f"self-window resolution must be unique; matches={len(matches)}"
            )
        return matches[0], discovery.receipt_id

    @staticmethod
    def build_exact_plan(target: LiveTarget) -> SupervisedPlan:
        return SupervisedPlan.from_steps(
            goal="A200-R6 controlled live minimize and immediate exact restore of its own console",
            steps=[
                {
                    "step_id": "live-self-minimize",
                    "capability_id": LIVE_ACCEPTED_CAPABILITY,
                    "action": LIVE_ACCEPTED_CAPABILITY,
                    "summary": "Minimize only the uniquely resolved A200-R6 console window",
                    "risk_tier": "REVERSIBLE",
                    "side_effect_class": "window_state",
                    "reversible": True,
                    "recovery_hint": "restore exact W132 preimage immediately",
                    "params_schema": {
                        "hwnd": target.hwnd,
                        "title": target.title,
                    },
                }
            ],
        )

    def run(self, *, human_approved: bool) -> LiveAcceptanceResult:
        if human_approved is not True:
            raise LiveAcceptanceDenied(
                "explicit human approval is required for A200-R6 live mutation"
            )

        target, discovery_receipt_id = self.resolve_self_window()
        plan = self.build_exact_plan(target)
        approval = ApprovalGrant.explicit_for(
            plan,
            approval_scope=["live-self-minimize"],
        )

        mutation = None
        restore = None
        verification_receipt_id = None

        try:
            mutation = self.mutation_binding.execute_one_reversible(
                plan,
                approval=approval,
            )
            if not mutation.ok or mutation.status != "succeeded":
                raise LiveAcceptanceDenied(
                    f"live mutation failed status={mutation.status}"
                )
            if mutation.recovery_token is None:
                raise LiveAcceptanceDenied(
                    "live mutation succeeded without mandatory recovery token"
                )
        finally:
            # If mutation succeeded and produced recovery material, restoration
            # is mandatory even when later checks fail.
            if mutation is not None and mutation.recovery_token is not None:
                restore = self.mutation_binding.restore(
                    mutation.recovery_token
                )

        if restore is None or not restore.ok or restore.status != "succeeded":
            raise LiveAcceptanceDenied(
                "automatic W132 restoration did not succeed"
            )

        verify = self.read_binding.execute_capability(
            "pc.discover_windows",
            params={},
            step_id="r6-post-restore-verify",
        )
        verification_receipt_id = verify.receipt_id

        visible = False
        if verify.ok and verify.status == "succeeded":
            for row in _rows_from_read_output(verify.output):
                try:
                    same_hwnd = int(row.get("hwnd") or 0) == target.hwnd
                except Exception:
                    same_hwnd = False
                same_title = str(row.get("title") or "").strip() == target.title
                if same_hwnd and same_title:
                    visible = True
                    break

        if not visible:
            raise LiveAcceptanceDenied(
                "post-restore exact HWND/title visibility verification failed"
            )

        return LiveAcceptanceResult(
            target=target,
            mutation=mutation,
            restore=restore,
            post_restore_visible=True,
            discovery_receipt_id=discovery_receipt_id,
            verification_receipt_id=verification_receipt_id,
        )


def assert_scope_is_live_self_window_only() -> None:
    if LIVE_ACCEPTED_CAPABILITY != "pc.minimize_window":
        raise RuntimeError("unexpected live mutation scope")
    if not LIVE_SELF_WINDOW_ONLY or not AUTO_RESTORE_REQUIRED:
        raise RuntimeError("R6 live safety flags are not strict")
