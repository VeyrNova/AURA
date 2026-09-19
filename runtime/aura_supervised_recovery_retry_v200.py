"""AURA A200-R8 bounded supervised recovery / retry / resume.

R8 adds an approval-gated retry controller around the already accepted R7
MissionEngine execution adapter.

Retry is intentionally narrow:
- only canonical R4 read actions are eligible;
- only a failed task with attempts < max_attempts is eligible;
- no A200 recovery token may be pending;
- the human approval is bound to mission_id, task_id, attempt number and an
  exact digest of the persisted failure snapshot;
- one retry approval authorizes one retry call only;
- mutation/restore/destructive actions are never retry candidates.

If failure occurs while a reversible mutation is outstanding, the R7 fail-safe
W132 recovery path takes priority and the mission is cancelled instead of retried.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from mission_engine import MissionEngine, Task
from runtime.aura_supervised_mission_executor_v200 import (
    A200SupervisedMissionExecutor,
    READ_ACTIONS,
)


A200_R8_MARKER = "AURA_A200_R8_BOUNDED_SUPERVISED_RECOVERY_RETRY_RESUME_V1"

MAX_SUPERVISED_RETRIES_PER_TASK = 1
RETRYABLE_ACTIONS = frozenset(READ_ACTIONS)

MUTATION_RETRY_ENABLED = False
AUTONOMOUS_RETRY_ENABLED = False
DESTRUCTIVE_EXECUTION_ENABLED = False
RECOVERY_PRECEDES_RETRY = True


class RetryApprovalError(PermissionError):
    pass


class RetryCandidateError(RuntimeError):
    pass


@dataclass(frozen=True)
class RetryCandidate:
    mission_id: str
    task_id: str
    task_key: str
    action: str
    failed_attempt: int
    max_attempts: int
    failure_digest: str


@dataclass(frozen=True)
class RetryApprovalGrant:
    mission_id: str
    task_id: str
    failed_attempt: int
    failure_digest: str
    explicit: bool = True

    @classmethod
    def explicit_for(cls, candidate: RetryCandidate) -> "RetryApprovalGrant":
        return cls(
            mission_id=candidate.mission_id,
            task_id=candidate.task_id,
            failed_attempt=candidate.failed_attempt,
            failure_digest=candidate.failure_digest,
            explicit=True,
        )


@dataclass(frozen=True)
class R8RunResult:
    mission_id: str
    mission_status: str
    phase: str
    task_id: str | None = None
    failure_digest: str | None = None
    emergency_restore_receipt_id: str | None = None


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _failure_snapshot(mission_id: str, task: Task) -> dict[str, Any]:
    return {
        "mission_id": mission_id,
        "task_id": task.task_id,
        "task_key": task.key,
        "action": task.tool_call.action,
        "status": task.status,
        "attempts": task.attempts,
        "max_attempts": task.max_attempts,
        "error": task.error,
        "evidence_ids": list(task.evidence_ids),
    }


def failure_digest(mission_id: str, task: Task) -> str:
    return hashlib.sha256(
        _canonical_json(_failure_snapshot(mission_id, task)).encode("utf-8")
    ).hexdigest()


class A200BoundedSupervisedRecovery:
    def __init__(
        self,
        *,
        mission_engine: MissionEngine,
        mission_executor: A200SupervisedMissionExecutor,
    ) -> None:
        self.engine = mission_engine
        self.executor = mission_executor
        self._retry_uses: dict[tuple[str, str], int] = {}

    def build_retryable_task_specs(
        self,
        *,
        hwnd: int,
        title: str,
    ) -> list[dict[str, Any]]:
        specs = self.executor.build_mission_task_specs(hwnd=hwnd, title=title)
        for spec in specs:
            if spec["key"] == "observe_before":
                spec["max_attempts"] = 2
            else:
                spec["max_attempts"] = 1
        return specs

    def inspect_retry_candidate(
        self,
        mission_id: str,
        *,
        task_id: str | None = None,
    ) -> RetryCandidate:
        if self.executor.recovery_pending:
            raise RetryCandidateError(
                "retry forbidden while reversible recovery token is pending"
            )

        mission = self.engine.get_mission(mission_id)
        failed = [
            task for task in mission.tasks.values()
            if task.status == "failed"
        ]
        if task_id is not None:
            failed = [task for task in failed if task.task_id == task_id]

        if len(failed) != 1:
            raise RetryCandidateError(
                f"expected exactly one failed retry candidate, found {len(failed)}"
            )

        task = failed[0]
        action = str(task.tool_call.action or "")
        if action not in RETRYABLE_ACTIONS:
            raise RetryCandidateError(
                f"action is not R8 retryable: {action!r}"
            )
        if task.attempts < 1:
            raise RetryCandidateError("failed task has no execution attempt")
        if task.attempts >= task.max_attempts:
            raise RetryCandidateError("MissionEngine retry bound reached")

        used = self._retry_uses.get((mission_id, task.task_id), 0)
        if used >= MAX_SUPERVISED_RETRIES_PER_TASK:
            raise RetryCandidateError("A200-R8 supervised retry bound reached")

        return RetryCandidate(
            mission_id=mission_id,
            task_id=task.task_id,
            task_key=task.key,
            action=action,
            failed_attempt=task.attempts,
            max_attempts=task.max_attempts,
            failure_digest=failure_digest(mission_id, task),
        )

    def approve_retry(
        self,
        candidate: RetryCandidate,
        *,
        approval: RetryApprovalGrant,
    ) -> Task:
        if approval.explicit is not True:
            raise RetryApprovalError("retry approval must be explicit")
        if approval.mission_id != candidate.mission_id:
            raise RetryApprovalError("retry approval mission mismatch")
        if approval.task_id != candidate.task_id:
            raise RetryApprovalError("retry approval task mismatch")
        if approval.failed_attempt != candidate.failed_attempt:
            raise RetryApprovalError("retry approval attempt mismatch")
        if approval.failure_digest != candidate.failure_digest:
            raise RetryApprovalError("retry approval failure digest mismatch")

        current = self.inspect_retry_candidate(
            candidate.mission_id,
            task_id=candidate.task_id,
        )
        if current.failure_digest != candidate.failure_digest:
            raise RetryApprovalError("stale retry approval: failure snapshot changed")

        retried = self.engine.retry_task(
            candidate.mission_id,
            candidate.task_id,
        )
        self._retry_uses[(candidate.mission_id, candidate.task_id)] = (
            self._retry_uses.get((candidate.mission_id, candidate.task_id), 0) + 1
        )

        # Canonical resume after explicit supervised retry scheduling.
        self.engine.resume(candidate.mission_id)
        return retried

    def run_until_pause_or_complete(
        self,
        mission_id: str,
        *,
        max_task_executions: int = 16,
    ) -> R8RunResult:
        executed = 0

        while executed < max_task_executions:
            mission = self.engine.get_mission(mission_id)

            waiting = [
                task for task in mission.tasks.values()
                if task.status == "waiting_confirmation"
            ]
            if waiting:
                return R8RunResult(
                    mission_id=mission_id,
                    mission_status=mission.status,
                    phase="waiting_confirmation",
                    task_id=waiting[0].task_id,
                )

            if mission.status in {"completed", "cancelled", "failed"}:
                return R8RunResult(
                    mission_id=mission_id,
                    mission_status=mission.status,
                    phase=mission.status,
                    emergency_restore_receipt_id=self.executor.last_emergency_restore_receipt_id,
                )

            if mission.tasks and all(
                task.status == "succeeded" for task in mission.tasks.values()
            ):
                completed = self.engine.complete(mission_id)
                return R8RunResult(
                    mission_id=mission_id,
                    mission_status=completed.status,
                    phase="completed",
                )

            ready = self.engine.next_ready_tasks(mission_id)

            if not ready:
                failed = [
                    task for task in self.engine.get_mission(mission_id).tasks.values()
                    if task.status == "failed"
                ]
                if failed:
                    if self.executor.recovery_pending:
                        receipt = self.executor._emergency_restore(
                            mission_id,
                            "R8 failure while recovery token pending",
                        )
                        cancelled = self.engine.cancel(mission_id)
                        return R8RunResult(
                            mission_id=mission_id,
                            mission_status=cancelled.status,
                            phase="failed_recovered",
                            task_id=failed[0].task_id,
                            emergency_restore_receipt_id=receipt,
                        )

                    try:
                        candidate = self.inspect_retry_candidate(
                            mission_id,
                            task_id=failed[0].task_id,
                        )
                    except RetryCandidateError:
                        cancelled = self.engine.cancel(mission_id)
                        return R8RunResult(
                            mission_id=mission_id,
                            mission_status=cancelled.status,
                            phase="failed_nonretryable",
                            task_id=failed[0].task_id,
                        )

                    return R8RunResult(
                        mission_id=mission_id,
                        mission_status=self.engine.get_mission(mission_id).status,
                        phase="waiting_retry_approval",
                        task_id=candidate.task_id,
                        failure_digest=candidate.failure_digest,
                    )

                raise RetryCandidateError(
                    "mission has no ready/waiting/failed task and is not complete"
                )

            for task in ready:
                current = self.executor._execute_task(
                    mission_id,
                    task.task_id,
                    user_confirmed=False,
                )
                executed += 1

                if current.status == "waiting_confirmation":
                    return R8RunResult(
                        mission_id=mission_id,
                        mission_status=self.engine.get_mission(mission_id).status,
                        phase="waiting_confirmation",
                        task_id=current.task_id,
                    )

                if current.status == "failed":
                    if self.executor.recovery_pending:
                        receipt = self.executor._emergency_restore(
                            mission_id,
                            "R8 task failure while reversible mutation outstanding",
                        )
                        cancelled = self.engine.cancel(mission_id)
                        return R8RunResult(
                            mission_id=mission_id,
                            mission_status=cancelled.status,
                            phase="failed_recovered",
                            task_id=current.task_id,
                            emergency_restore_receipt_id=receipt,
                        )

                    try:
                        candidate = self.inspect_retry_candidate(
                            mission_id,
                            task_id=current.task_id,
                        )
                    except RetryCandidateError:
                        cancelled = self.engine.cancel(mission_id)
                        return R8RunResult(
                            mission_id=mission_id,
                            mission_status=cancelled.status,
                            phase="failed_nonretryable",
                            task_id=current.task_id,
                        )

                    return R8RunResult(
                        mission_id=mission_id,
                        mission_status=self.engine.get_mission(mission_id).status,
                        phase="waiting_retry_approval",
                        task_id=candidate.task_id,
                        failure_digest=candidate.failure_digest,
                    )

        if self.executor.recovery_pending:
            receipt = self.executor._emergency_restore(
                mission_id,
                "R8 execution bound exceeded",
            )
            self.engine.cancel(mission_id)
            return R8RunResult(
                mission_id=mission_id,
                mission_status="cancelled",
                phase="bound_exceeded_recovered",
                emergency_restore_receipt_id=receipt,
            )

        raise RetryCandidateError("R8 maximum task execution bound exceeded")


def assert_r8_safety_contract() -> None:
    if MAX_SUPERVISED_RETRIES_PER_TASK != 1:
        raise RuntimeError("R8 retry bound must remain exactly one")
    if MUTATION_RETRY_ENABLED:
        raise RuntimeError("mutation retry must remain disabled")
    if AUTONOMOUS_RETRY_ENABLED:
        raise RuntimeError("autonomous retry must remain disabled")
    if DESTRUCTIVE_EXECUTION_ENABLED:
        raise RuntimeError("destructive execution must remain disabled")
    if not RECOVERY_PRECEDES_RETRY:
        raise RuntimeError("recovery must take precedence over retry")
