"""AURA A200-R15 UI/conversation command bridge.

R15 is a presentation/command companion over the certified R14 supervised
runtime ingress. It does not become a mission, policy, receipt, or integration
authority.

It provides a narrow UI/conversation contract:
- runtime.status
- pc.read_foreground
- pc.prepare_minimize_window
- approval.present
- approval.confirm
- mission.cancel

All state-changing work still flows:
R15 -> R14 -> R13 -> MissionEngine -> R11/R9/R7/R5 -> IntegrationRegistry.

R15 adds a presentation digest so a confirmation is bound to the exact
approval card shown to the user. Supervised cancellation persists through
MissionEngine and terminalizes pending approval challenges without dispatching
the mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from runtime.aura_supervised_runtime_ingress_v200 import (
    A200SupervisedRuntimeIngress,
    ApprovalBridgeError,
    ApprovalChallenge,
    ApprovalGrant,
)


A200_R15_MARKER = "AURA_A200_R15_UI_CONVERSATION_COMMAND_BRIDGE_APPROVAL_CANCELLATION_V1"

STRUCTURED_UI_COMMANDS_ONLY = True
APPROVAL_PRESENTATION_DIGEST_REQUIRED = True
EXPLICIT_APPROVAL_CONFIRMATION_REQUIRED = True
EXPLICIT_CANCELLATION_CONFIRMATION_REQUIRED = True
SUPERVISED_CANCELLATION_REQUIRED = True
MISSIONENGINE_CANCEL_AUTHORITY_REQUIRED = True

NATURAL_LANGUAGE_DIRECT_EXECUTION_ENABLED = False
ARBITRARY_COMMAND_EXECUTION_ENABLED = False
ARBITRARY_TOOL_INGRESS_ENABLED = False
AUTO_APPROVAL_ENABLED = False
AUTO_CANCEL_ENABLED = False
AUTONOMOUS_RETRY_ENABLED = False
AUTONOMOUS_MUTATION_ENABLED = False
DESTRUCTIVE_EXECUTION_ENABLED = False


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class UiCommandBridgeError(RuntimeError):
    pass


class UiApprovalPresentationError(PermissionError):
    pass


class UiCancellationError(PermissionError):
    pass


@dataclass(frozen=True)
class ApprovalPresentation:
    approval_id: str
    session_id: str
    mission_id: str
    task_id: str
    plan_revision: int
    action: str
    target_title: str | None
    target_hwnd: int | None
    risk: str
    reversible: bool
    requires_explicit_confirmation: bool
    challenge_digest: str
    presentation_digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "session_id": self.session_id,
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "plan_revision": int(self.plan_revision),
            "action": self.action,
            "target_title": self.target_title,
            "target_hwnd": self.target_hwnd,
            "risk": self.risk,
            "reversible": self.reversible,
            "requires_explicit_confirmation": self.requires_explicit_confirmation,
            "challenge_digest": self.challenge_digest,
        }

    def recompute_digest(self) -> str:
        return _sha256(self.payload())


@dataclass(frozen=True)
class BridgeResponse:
    kind: str
    ok: bool
    payload: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "ok": bool(self.ok),
            "payload": dict(self.payload),
        }


class A200UiConversationCommandBridge:
    ALLOWED_COMMANDS = frozenset(
        {
            "runtime.status",
            "pc.read_foreground",
            "pc.prepare_minimize_window",
            "approval.present",
            "approval.confirm",
            "mission.cancel",
        }
    )

    def __init__(self, *, ingress: A200SupervisedRuntimeIngress) -> None:
        self.ingress = ingress
        self.runtime = ingress.runtime

    @staticmethod
    def _task_params(task: Any) -> Mapping[str, Any]:
        params = getattr(getattr(task, "tool_call", None), "params", None)
        return {} if not isinstance(params, Mapping) else dict(params)

    def _challenge_for_current_session(
        self,
        approval_id: str,
    ) -> ApprovalChallenge:
        challenge = self.ingress.approval_store.get(str(approval_id))
        if challenge is None:
            raise UiApprovalPresentationError("approval challenge not found")
        if challenge.state != "pending":
            raise UiApprovalPresentationError(
                f"approval challenge is not pending: {challenge.state}"
            )
        if challenge.session_id != self.runtime.session_id:
            raise UiApprovalPresentationError(
                "approval challenge belongs to another runtime session"
            )
        if challenge.recompute_digest() != challenge.challenge_digest:
            raise UiApprovalPresentationError(
                "stored approval challenge digest is corrupted"
            )
        return challenge

    def render_approval(
        self,
        challenge: ApprovalChallenge,
    ) -> ApprovalPresentation:
        current = self._challenge_for_current_session(
            challenge.approval_id
        )
        if current.challenge_digest != challenge.challenge_digest:
            raise UiApprovalPresentationError(
                "approval challenge changed before presentation"
            )

        mission = self.runtime.engine.get_mission(current.mission_id)
        if mission.plan is None:
            raise UiApprovalPresentationError("mission plan is unavailable")
        task = mission.tasks.get(current.task_id)
        if task is None:
            raise UiApprovalPresentationError("approval task is unavailable")
        if str(task.status) != "waiting_confirmation":
            raise UiApprovalPresentationError(
                "approval task is no longer waiting_confirmation"
            )
        if int(mission.plan.revision) != int(current.plan_revision):
            raise UiApprovalPresentationError(
                "mission plan changed before presentation"
            )
        if str(task.tool_call.action) != current.action:
            raise UiApprovalPresentationError(
                "approval action changed before presentation"
            )

        params = self._task_params(task)
        target_title = (
            None
            if params.get("title") is None
            else str(params.get("title"))
        )
        try:
            target_hwnd = (
                None
                if params.get("hwnd") is None
                else int(params.get("hwnd"))
            )
        except Exception as exc:
            raise UiApprovalPresentationError(
                "invalid target hwnd in canonical task"
            ) from exc

        base = {
            "approval_id": current.approval_id,
            "session_id": current.session_id,
            "mission_id": current.mission_id,
            "task_id": current.task_id,
            "plan_revision": int(current.plan_revision),
            "action": current.action,
            "target_title": target_title,
            "target_hwnd": target_hwnd,
            "risk": "reversible_mutation",
            "reversible": True,
            "requires_explicit_confirmation": True,
            "challenge_digest": current.challenge_digest,
        }
        digest = _sha256(base)
        return ApprovalPresentation(
            approval_id=current.approval_id,
            session_id=current.session_id,
            mission_id=current.mission_id,
            task_id=current.task_id,
            plan_revision=int(current.plan_revision),
            action=current.action,
            target_title=target_title,
            target_hwnd=target_hwnd,
            risk="reversible_mutation",
            reversible=True,
            requires_explicit_confirmation=True,
            challenge_digest=current.challenge_digest,
            presentation_digest=digest,
        )

    def _present_current_mission_approval(
        self,
        mission_id: str,
    ) -> ApprovalPresentation:
        pending = [
            challenge
            for challenge in self.ingress.approval_store.pending_for_session(
                self.runtime.session_id
            )
            if challenge.mission_id == mission_id
        ]
        if len(pending) == 0:
            challenge = self.ingress.issue_approval_challenge(
                mission_id
            )
        elif len(pending) == 1:
            challenge = pending[0]
        else:
            raise UiApprovalPresentationError(
                "multiple pending approval challenges for one mission"
            )
        return self.render_approval(challenge)

    def _status_payload(self) -> dict[str, Any]:
        status = self.ingress.status_surface()
        presentations: list[dict[str, Any]] = []
        for approval_id in status.pending_approval_ids:
            try:
                challenge = self._challenge_for_current_session(
                    approval_id
                )
                presentation = self.render_approval(challenge)
                presentations.append(
                    {
                        **presentation.payload(),
                        "presentation_digest": presentation.presentation_digest,
                    }
                )
            except Exception:
                # Status remains read-only/fail-closed. A malformed pending
                # challenge is not promoted to an actionable card.
                continue

        return {
            "session_id": status.session_id,
            "read_only_ready": status.read_only_ready,
            "mutation_ready": status.mutation_ready,
            "startup_recovered_missions": list(
                status.startup_recovered_missions
            ),
            "startup_supervision_required": list(
                status.startup_supervision_required
            ),
            "startup_failures": list(status.startup_failures),
            "tracked_missions": [
                dict(item) for item in status.tracked_missions
            ],
            "approval_counts": dict(status.approval_counts),
            "pending_approvals": presentations,
        }

    def _invalidate_pending_approvals_for_mission(
        self,
        mission_id: str,
        *,
        reason: str,
    ) -> int:
        pending = [
            challenge
            for challenge in self.ingress.approval_store.pending_for_session(
                self.runtime.session_id
            )
            if challenge.mission_id == mission_id
        ]
        invalidated = 0
        for challenge in pending:
            try:
                self.ingress.approval_store.begin_consume(
                    approval_id=challenge.approval_id,
                    session_id=self.runtime.session_id,
                    challenge_digest=challenge.challenge_digest,
                )
                self.ingress.approval_store.mark_failed(
                    challenge.approval_id,
                    UiCancellationError(reason),
                )
                invalidated += 1
            except ApprovalBridgeError:
                pass
        return invalidated

    def cancel_mission(
        self,
        mission_id: str,
        *,
        explicit_confirmation: bool,
    ) -> BridgeResponse:
        if explicit_confirmation is not True:
            raise UiCancellationError(
                "explicit cancellation confirmation is required"
            )

        mission_id = str(mission_id or "").strip()
        if not mission_id:
            raise UiCancellationError("mission_id is required")

        mission = self.runtime.engine.get_mission(mission_id)
        before = str(mission.status)

        pending_recovery = self.runtime.crash_journal.get_pending(
            mission_id
        )
        recovery_receipt_id = None
        if pending_recovery is not None:
            recovered = self.runtime.executor.recover_after_restart(
                mission_id
            )
            recovery_receipt_id = str(
                recovered.restore_receipt_id or ""
            ) or None
            after = str(
                self.runtime.engine.get_mission(mission_id).status
            )
            self.runtime._track_current_mission(
                mission_id,
                recovery_receipt_id=recovery_receipt_id,
            )
            invalidated = self._invalidate_pending_approvals_for_mission(
                mission_id,
                reason="mission cancelled by supervised recovery",
            )
            self.runtime.refresh_readiness()
            return BridgeResponse(
                kind="mission.cancelled",
                ok=True,
                payload={
                    "mission_id": mission_id,
                    "status_before": before,
                    "status_after": after,
                    "recovery_performed": True,
                    "recovery_receipt_id": recovery_receipt_id,
                    "invalidated_approvals": invalidated,
                },
            )

        if before in {"completed", "cancelled", "failed"}:
            invalidated = self._invalidate_pending_approvals_for_mission(
                mission_id,
                reason="terminal mission approval invalidation",
            )
            self.runtime.refresh_readiness()
            return BridgeResponse(
                kind="mission.terminal",
                ok=True,
                payload={
                    "mission_id": mission_id,
                    "status_before": before,
                    "status_after": before,
                    "recovery_performed": False,
                    "recovery_receipt_id": None,
                    "invalidated_approvals": invalidated,
                },
            )

        cancelled = self.runtime.engine.cancel(mission_id)
        self.runtime._track_current_mission(mission_id)
        invalidated = self._invalidate_pending_approvals_for_mission(
            mission_id,
            reason="mission cancelled explicitly by user",
        )
        self.runtime.refresh_readiness()

        return BridgeResponse(
            kind="mission.cancelled",
            ok=True,
            payload={
                "mission_id": mission_id,
                "status_before": before,
                "status_after": str(cancelled.status),
                "recovery_performed": False,
                "recovery_receipt_id": None,
                "invalidated_approvals": invalidated,
            },
        )

    def handle(
        self,
        command: Mapping[str, Any],
    ) -> BridgeResponse:
        if not isinstance(command, Mapping):
            raise UiCommandBridgeError(
                "structured command mapping required"
            )
        command_type = str(command.get("type") or "").strip()
        if command_type not in self.ALLOWED_COMMANDS:
            raise UiCommandBridgeError(
                f"unsupported structured command: {command_type!r}"
            )

        if command_type == "runtime.status":
            return BridgeResponse(
                kind="runtime.status",
                ok=True,
                payload=self._status_payload(),
            )

        if command_type == "pc.read_foreground":
            result = self.ingress.submit_read(
                "pc.get_foreground_window",
                request_id=str(
                    command.get("request_id")
                    or "r15-ui-read-foreground"
                ),
            )
            return BridgeResponse(
                kind="pc.read_foreground",
                ok=bool(result.ok),
                payload={
                    "status": str(result.status),
                    "receipt_id": result.receipt_id,
                    "output": result.output,
                },
            )

        if command_type == "pc.prepare_minimize_window":
            try:
                hwnd = int(command.get("hwnd"))
            except Exception as exc:
                raise UiCommandBridgeError(
                    "pc.prepare_minimize_window requires integer hwnd"
                ) from exc
            title = str(command.get("title") or "").strip()
            if hwnd <= 0 or not title:
                raise UiCommandBridgeError(
                    "pc.prepare_minimize_window requires exact hwnd/title"
                )
            progress = self.ingress.submit_reversible_window_mission(
                hwnd=hwnd,
                title=title,
                goal=str(
                    command.get("goal")
                    or "AURA supervised minimize-window request"
                ),
            )
            if (
                progress.phase != "waiting_confirmation"
                or progress.approval_challenge is None
            ):
                raise UiCommandBridgeError(
                    "reversible mission did not reach approval presentation"
                )
            presentation = self.render_approval(
                progress.approval_challenge
            )
            return BridgeResponse(
                kind="approval.required",
                ok=True,
                payload={
                    "mission_id": progress.mission_id,
                    "mission_status": progress.mission_status,
                    "phase": progress.phase,
                    "approval": {
                        **presentation.payload(),
                        "presentation_digest": presentation.presentation_digest,
                    },
                },
            )

        if command_type == "approval.present":
            mission_id = str(
                command.get("mission_id") or ""
            ).strip()
            if not mission_id:
                raise UiCommandBridgeError(
                    "approval.present requires mission_id"
                )
            presentation = self._present_current_mission_approval(
                mission_id
            )
            return BridgeResponse(
                kind="approval.required",
                ok=True,
                payload={
                    "mission_id": mission_id,
                    "approval": {
                        **presentation.payload(),
                        "presentation_digest": presentation.presentation_digest,
                    },
                },
            )

        if command_type == "approval.confirm":
            if command.get("confirm") is not True:
                raise UiApprovalPresentationError(
                    "explicit approval confirmation is required"
                )
            approval_id = str(
                command.get("approval_id") or ""
            ).strip()
            presentation_digest = str(
                command.get("presentation_digest") or ""
            ).strip()
            if not approval_id or not presentation_digest:
                raise UiApprovalPresentationError(
                    "approval_id and presentation_digest are required"
                )

            challenge = self._challenge_for_current_session(
                approval_id
            )
            current = self.render_approval(challenge)
            if current.presentation_digest != presentation_digest:
                raise UiApprovalPresentationError(
                    "approval presentation digest mismatch"
                )

            result = self.ingress.approve(
                ApprovalGrant.explicit_for(challenge)
            )
            return BridgeResponse(
                kind="approval.completed",
                ok=True,
                payload={
                    "mission_id": result.mission_id,
                    "mission_status": result.mission_status,
                    "phase": result.phase,
                    "approval_id": approval_id,
                },
            )

        if command_type == "mission.cancel":
            return self.cancel_mission(
                str(command.get("mission_id") or ""),
                explicit_confirmation=(
                    command.get("confirm_cancel") is True
                ),
            )

        raise UiCommandBridgeError("unreachable command branch")


def assert_r15_safety_contract() -> None:
    if not STRUCTURED_UI_COMMANDS_ONLY:
        raise RuntimeError("R15 commands must remain structured-only")
    if not APPROVAL_PRESENTATION_DIGEST_REQUIRED:
        raise RuntimeError("approval presentation digest is mandatory")
    if not EXPLICIT_APPROVAL_CONFIRMATION_REQUIRED:
        raise RuntimeError("explicit approval confirmation is mandatory")
    if not EXPLICIT_CANCELLATION_CONFIRMATION_REQUIRED:
        raise RuntimeError("explicit cancellation confirmation is mandatory")
    if not SUPERVISED_CANCELLATION_REQUIRED:
        raise RuntimeError("supervised cancellation is mandatory")
    if not MISSIONENGINE_CANCEL_AUTHORITY_REQUIRED:
        raise RuntimeError("MissionEngine must remain cancellation authority")
    if NATURAL_LANGUAGE_DIRECT_EXECUTION_ENABLED:
        raise RuntimeError("direct natural-language execution must remain disabled")
    if ARBITRARY_COMMAND_EXECUTION_ENABLED or ARBITRARY_TOOL_INGRESS_ENABLED:
        raise RuntimeError("arbitrary command/tool ingress must remain disabled")
    if AUTO_APPROVAL_ENABLED or AUTO_CANCEL_ENABLED:
        raise RuntimeError("auto approval/cancel must remain disabled")
    if AUTONOMOUS_RETRY_ENABLED or AUTONOMOUS_MUTATION_ENABLED:
        raise RuntimeError("autonomous retry/mutation must remain disabled")
    if DESTRUCTIVE_EXECUTION_ENABLED:
        raise RuntimeError("destructive execution must remain disabled")
