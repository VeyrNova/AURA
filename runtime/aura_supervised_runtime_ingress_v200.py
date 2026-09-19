"""AURA A200-R14 supervised runtime ingress + approval bridge + status surface.

R14 is a companion facade over the certified R13 persistent runtime. It does
not become a mission authority and does not widen the Windows capability set.

It provides:
- structured read-only ingress through R13/R4;
- structured reversible-window mission ingress through R13/R11/R9/R7/R5;
- durable, exact-bound, one-use approval challenges;
- session-bound explicit approval grants;
- a read-only status surface suitable for the UI.

Safety:
- no arbitrary tool ingress;
- no raw shell/process execution;
- no automatic approval;
- no approval reuse after session restart;
- no autonomous retry or mutation;
- no close/terminate/destructive capability.
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping
import uuid

from runtime.aura_persistent_runtime_bootstrap_v200 import (
    A200PersistentRuntimeBootstrap,
    RuntimeMutationBlocked,
)


A200_R14_MARKER = "AURA_A200_R14_SUPERVISED_RUNTIME_INGRESS_EXPLICIT_APPROVAL_STATUS_V1"

STRUCTURED_INGRESS_ONLY = True
EXPLICIT_APPROVAL_BRIDGE_REQUIRED = True
APPROVAL_DURABILITY_REQUIRED = True
APPROVAL_EXACT_BINDING_REQUIRED = True
APPROVAL_ONE_USE = True
APPROVAL_SESSION_BOUND = True
READ_ONLY_STATUS_SURFACE_REQUIRED = True

ARBITRARY_TOOL_INGRESS_ENABLED = False
AUTO_APPROVAL_ENABLED = False
APPROVAL_REUSE_AFTER_RESTART_ENABLED = False
AUTONOMOUS_RETRY_ENABLED = False
AUTONOMOUS_MUTATION_ENABLED = False
LEASE_STEAL_ENABLED = False
DESTRUCTIVE_EXECUTION_ENABLED = False


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


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


def _params_digest(params: Mapping[str, Any] | None) -> str:
    return _sha256(dict(params or {}))


class RuntimeIngressError(RuntimeError):
    pass


class ApprovalBridgeError(PermissionError):
    pass


@dataclass(frozen=True)
class ApprovalChallenge:
    approval_id: str
    session_id: str
    mission_id: str
    task_id: str
    plan_revision: int
    action: str
    params_digest: str
    challenge_digest: str
    state: str
    created_at: str
    consumed_at: str | None = None
    failure: str | None = None

    @staticmethod
    def payload(
        *,
        approval_id: str,
        session_id: str,
        mission_id: str,
        task_id: str,
        plan_revision: int,
        action: str,
        params_digest: str,
    ) -> dict[str, Any]:
        return {
            "approval_id": approval_id,
            "session_id": session_id,
            "mission_id": mission_id,
            "task_id": task_id,
            "plan_revision": int(plan_revision),
            "action": action,
            "params_digest": params_digest,
        }

    def recompute_digest(self) -> str:
        return _sha256(
            self.payload(
                approval_id=self.approval_id,
                session_id=self.session_id,
                mission_id=self.mission_id,
                task_id=self.task_id,
                plan_revision=self.plan_revision,
                action=self.action,
                params_digest=self.params_digest,
            )
        )


@dataclass(frozen=True)
class ApprovalGrant:
    approval_id: str
    challenge_digest: str
    explicit_confirmation: bool

    @classmethod
    def explicit_for(cls, challenge: ApprovalChallenge) -> "ApprovalGrant":
        return cls(
            approval_id=challenge.approval_id,
            challenge_digest=challenge.challenge_digest,
            explicit_confirmation=True,
        )


@dataclass(frozen=True)
class MissionIngressResult:
    mission_id: str
    phase: str
    mission_status: str
    approval_challenge: ApprovalChallenge | None


@dataclass(frozen=True)
class RuntimeStatusSurface:
    session_id: str
    read_only_ready: bool
    mutation_ready: bool
    startup_recovered_missions: tuple[str, ...]
    startup_supervision_required: tuple[str, ...]
    startup_failures: tuple[str, ...]
    tracked_missions: tuple[Mapping[str, Any], ...]
    approval_counts: Mapping[str, int]
    pending_approval_ids: tuple[str, ...]


class R14ApprovalStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self):
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=15.0,
            isolation_level=None,
        )
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA synchronous=FULL;

                CREATE TABLE IF NOT EXISTS r14_approval_challenges (
                    approval_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    mission_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    plan_revision INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    params_digest TEXT NOT NULL,
                    challenge_digest TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    consumed_at TEXT,
                    failure TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_r14_approval_state_session
                ON r14_approval_challenges(state, session_id, created_at);

                CREATE INDEX IF NOT EXISTS idx_r14_approval_mission_task
                ON r14_approval_challenges(mission_id, task_id, created_at);
                """
            )

    @staticmethod
    def _from_row(row: sqlite3.Row | None) -> ApprovalChallenge | None:
        if row is None:
            return None
        return ApprovalChallenge(
            approval_id=str(row["approval_id"]),
            session_id=str(row["session_id"]),
            mission_id=str(row["mission_id"]),
            task_id=str(row["task_id"]),
            plan_revision=int(row["plan_revision"]),
            action=str(row["action"]),
            params_digest=str(row["params_digest"]),
            challenge_digest=str(row["challenge_digest"]),
            state=str(row["state"]),
            created_at=str(row["created_at"]),
            consumed_at=(
                None if row["consumed_at"] is None else str(row["consumed_at"])
            ),
            failure=None if row["failure"] is None else str(row["failure"]),
        )

    def issue(
        self,
        *,
        session_id: str,
        mission_id: str,
        task_id: str,
        plan_revision: int,
        action: str,
        params_digest: str,
    ) -> ApprovalChallenge:
        approval_id = "apr_" + uuid.uuid4().hex
        payload = ApprovalChallenge.payload(
            approval_id=approval_id,
            session_id=session_id,
            mission_id=mission_id,
            task_id=task_id,
            plan_revision=plan_revision,
            action=action,
            params_digest=params_digest,
        )
        challenge_digest = _sha256(payload)
        created_at = _utc_now()

        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                UPDATE r14_approval_challenges
                   SET state='superseded', failure='new challenge issued'
                 WHERE session_id=?
                   AND mission_id=?
                   AND task_id=?
                   AND state='pending'
                """,
                (session_id, mission_id, task_id),
            )
            conn.execute(
                """
                INSERT INTO r14_approval_challenges(
                    approval_id, session_id, mission_id, task_id,
                    plan_revision, action, params_digest,
                    challenge_digest, state, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (
                    approval_id,
                    session_id,
                    mission_id,
                    task_id,
                    int(plan_revision),
                    action,
                    params_digest,
                    challenge_digest,
                    created_at,
                ),
            )
            conn.commit()

        return ApprovalChallenge(
            approval_id=approval_id,
            session_id=session_id,
            mission_id=mission_id,
            task_id=task_id,
            plan_revision=int(plan_revision),
            action=action,
            params_digest=params_digest,
            challenge_digest=challenge_digest,
            state="pending",
            created_at=created_at,
        )

    def get(self, approval_id: str) -> ApprovalChallenge | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT *
                  FROM r14_approval_challenges
                 WHERE approval_id=?
                """,
                (approval_id,),
            ).fetchone()
        return self._from_row(row)

    def invalidate_foreign_pending_sessions(self, current_session_id: str) -> int:
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                """
                UPDATE r14_approval_challenges
                   SET state='stale_session',
                       failure='runtime session changed before approval'
                 WHERE state='pending'
                   AND session_id<>?
                """,
                (current_session_id,),
            )
            conn.commit()
            return int(cur.rowcount or 0)

    def begin_consume(
        self,
        *,
        approval_id: str,
        session_id: str,
        challenge_digest: str,
    ) -> ApprovalChallenge:
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT *
                  FROM r14_approval_challenges
                 WHERE approval_id=?
                """,
                (approval_id,),
            ).fetchone()
            challenge = self._from_row(row)
            if challenge is None:
                conn.rollback()
                raise ApprovalBridgeError("approval challenge not found")
            if challenge.state != "pending":
                conn.rollback()
                raise ApprovalBridgeError(
                    f"approval challenge is not pending: {challenge.state}"
                )
            if challenge.session_id != session_id:
                conn.rollback()
                raise ApprovalBridgeError("approval session binding mismatch")
            if challenge.challenge_digest != challenge_digest:
                conn.rollback()
                raise ApprovalBridgeError("approval digest mismatch")
            cur = conn.execute(
                """
                UPDATE r14_approval_challenges
                   SET state='consuming'
                 WHERE approval_id=?
                   AND state='pending'
                """,
                (approval_id,),
            )
            if int(cur.rowcount or 0) != 1:
                conn.rollback()
                raise ApprovalBridgeError("approval challenge race detected")
            conn.commit()

        updated = self.get(approval_id)
        if updated is None:
            raise ApprovalBridgeError("approval challenge disappeared")
        return updated

    def mark_consumed(self, approval_id: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                """
                UPDATE r14_approval_challenges
                   SET state='consumed', consumed_at=?
                 WHERE approval_id=?
                   AND state='consuming'
                """,
                (_utc_now(), approval_id),
            )
            if int(cur.rowcount or 0) != 1:
                conn.rollback()
                raise ApprovalBridgeError("approval consume transition failed")
            conn.commit()

    def mark_failed(self, approval_id: str, exc: Exception) -> None:
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                UPDATE r14_approval_challenges
                   SET state='failed',
                       failure=?,
                       consumed_at=?
                 WHERE approval_id=?
                   AND state='consuming'
                """,
                (
                    f"{type(exc).__name__}: {exc}",
                    _utc_now(),
                    approval_id,
                ),
            )
            conn.commit()

    def count(self, state: str | None = None) -> int:
        with closing(self._connect()) as conn:
            if state is None:
                row = conn.execute(
                    "SELECT COUNT(*) AS n FROM r14_approval_challenges"
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT COUNT(*) AS n
                      FROM r14_approval_challenges
                     WHERE state=?
                    """,
                    (state,),
                ).fetchone()
        return int(row["n"])

    def pending_for_session(self, session_id: str) -> list[ApprovalChallenge]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT *
                  FROM r14_approval_challenges
                 WHERE session_id=?
                   AND state='pending'
                 ORDER BY created_at, approval_id
                """,
                (session_id,),
            ).fetchall()
        return [self._from_row(row) for row in rows if row is not None]


class A200SupervisedRuntimeIngress:
    def __init__(
        self,
        *,
        runtime: A200PersistentRuntimeBootstrap,
        approval_store: R14ApprovalStore | None = None,
    ) -> None:
        self.runtime = runtime
        self.approval_store = approval_store or R14ApprovalStore(
            runtime.state_root / "ingress_approvals.sqlite3"
        )
        self.approval_store.invalidate_foreign_pending_sessions(
            runtime.session_id
        )

    def submit_read(
        self,
        capability_id: str,
        *,
        params: Mapping[str, Any] | None = None,
        request_id: str = "r14-read",
    ) -> Any:
        capability = str(capability_id or "")
        if capability not in {
            "pc.discover_windows",
            "pc.discover_processes",
            "pc.get_foreground_window",
        }:
            raise RuntimeIngressError(
                "R14 read ingress only accepts the certified R4 read allowlist"
            )
        return self.runtime.execute_read_only(
            capability,
            params=dict(params or {}),
            step_id=request_id,
        )

    def _current_waiting_task(self, mission_id: str):
        mission = self.runtime.engine.get_mission(mission_id)
        if mission.plan is None:
            raise ApprovalBridgeError("mission has no canonical plan")
        waiting = [
            task
            for task in mission.tasks.values()
            if str(task.status) == "waiting_confirmation"
        ]
        if len(waiting) != 1:
            raise ApprovalBridgeError(
                "exactly one canonical waiting_confirmation task required"
            )
        return mission, waiting[0]

    def issue_approval_challenge(
        self,
        mission_id: str,
    ) -> ApprovalChallenge:
        mission, task = self._current_waiting_task(mission_id)
        return self.approval_store.issue(
            session_id=self.runtime.session_id,
            mission_id=mission_id,
            task_id=task.task_id,
            plan_revision=int(mission.plan.revision),
            action=str(task.tool_call.action),
            params_digest=_params_digest(task.tool_call.params),
        )

    def submit_reversible_window_mission(
        self,
        *,
        hwnd: int,
        title: str,
        goal: str = "A200-R14 supervised reversible window request",
    ) -> MissionIngressResult:
        mission_id = self.runtime.create_supervised_window_mission(
            hwnd=int(hwnd),
            title=str(title),
            goal=goal,
        )
        run = self.runtime.run_tracked_until_pause_or_complete(mission_id)
        mission = self.runtime.engine.get_mission(mission_id)
        challenge = None
        if run.phase == "waiting_confirmation":
            challenge = self.issue_approval_challenge(mission_id)
        return MissionIngressResult(
            mission_id=mission_id,
            phase=str(run.phase),
            mission_status=str(mission.status),
            approval_challenge=challenge,
        )

    def approve(
        self,
        grant: ApprovalGrant,
    ) -> MissionIngressResult:
        if grant.explicit_confirmation is not True:
            raise ApprovalBridgeError("explicit approval flag is required")

        challenge = self.approval_store.get(grant.approval_id)
        if challenge is None:
            raise ApprovalBridgeError("approval challenge not found")
        if challenge.state != "pending":
            raise ApprovalBridgeError(
                f"approval challenge is not pending: {challenge.state}"
            )
        if challenge.session_id != self.runtime.session_id:
            raise ApprovalBridgeError("approval belongs to another runtime session")
        if challenge.challenge_digest != grant.challenge_digest:
            raise ApprovalBridgeError("approval grant digest mismatch")
        if challenge.recompute_digest() != challenge.challenge_digest:
            raise ApprovalBridgeError("stored approval challenge digest corrupted")

        mission, task = self._current_waiting_task(challenge.mission_id)
        if task.task_id != challenge.task_id:
            raise ApprovalBridgeError("waiting task identity changed")
        if int(mission.plan.revision) != int(challenge.plan_revision):
            raise ApprovalBridgeError("mission plan revision changed")
        if str(task.tool_call.action) != challenge.action:
            raise ApprovalBridgeError("waiting action changed")
        if _params_digest(task.tool_call.params) != challenge.params_digest:
            raise ApprovalBridgeError("waiting task params changed")

        self.approval_store.begin_consume(
            approval_id=challenge.approval_id,
            session_id=self.runtime.session_id,
            challenge_digest=challenge.challenge_digest,
        )

        try:
            run = self.runtime.explicitly_confirm_tracked_mission(
                challenge.mission_id,
                explicit_confirmation=True,
            )
        except Exception as exc:
            self.approval_store.mark_failed(
                challenge.approval_id,
                exc,
            )
            raise

        self.approval_store.mark_consumed(challenge.approval_id)
        mission = self.runtime.engine.get_mission(challenge.mission_id)
        return MissionIngressResult(
            mission_id=challenge.mission_id,
            phase=str(run.phase),
            mission_status=str(mission.status),
            approval_challenge=None,
        )

    def status_surface(self) -> RuntimeStatusSurface:
        tracked: list[Mapping[str, Any]] = []
        for mission_id in self.runtime.session_store.unfinished_mission_ids():
            try:
                mission = self.runtime.engine.get_mission(mission_id)
                waiting = [
                    task.task_id
                    for task in mission.tasks.values()
                    if str(task.status) == "waiting_confirmation"
                ]
                tracked.append(
                    {
                        "mission_id": mission_id,
                        "status": str(mission.status),
                        "waiting_confirmation": bool(waiting),
                        "waiting_task_id": waiting[0] if len(waiting) == 1 else None,
                    }
                )
            except Exception:
                tracked.append(
                    {
                        "mission_id": mission_id,
                        "status": "unavailable",
                        "waiting_confirmation": False,
                        "waiting_task_id": None,
                    }
                )

        states = (
            "pending",
            "consuming",
            "consumed",
            "failed",
            "stale_session",
            "superseded",
        )
        counts = {
            state: self.approval_store.count(state=state)
            for state in states
        }
        pending = self.approval_store.pending_for_session(
            self.runtime.session_id
        )
        snapshot = self.runtime.startup_snapshot
        return RuntimeStatusSurface(
            session_id=self.runtime.session_id,
            read_only_ready=self.runtime.read_only_ready,
            mutation_ready=self.runtime.mutation_ready,
            startup_recovered_missions=tuple(snapshot.recovered_missions),
            startup_supervision_required=tuple(
                snapshot.supervision_required
            ),
            startup_failures=tuple(snapshot.startup_failures),
            tracked_missions=tuple(tracked),
            approval_counts=counts,
            pending_approval_ids=tuple(
                item.approval_id for item in pending
            ),
        )


def assert_r14_safety_contract() -> None:
    if not STRUCTURED_INGRESS_ONLY:
        raise RuntimeError("R14 ingress must remain structured-only")
    if not EXPLICIT_APPROVAL_BRIDGE_REQUIRED:
        raise RuntimeError("explicit approval bridge is mandatory")
    if not APPROVAL_DURABILITY_REQUIRED:
        raise RuntimeError("approval durability is mandatory")
    if not APPROVAL_EXACT_BINDING_REQUIRED:
        raise RuntimeError("approval exact binding is mandatory")
    if not APPROVAL_ONE_USE or not APPROVAL_SESSION_BOUND:
        raise RuntimeError("approval must remain one-use and session-bound")
    if not READ_ONLY_STATUS_SURFACE_REQUIRED:
        raise RuntimeError("status surface is mandatory")
    if ARBITRARY_TOOL_INGRESS_ENABLED or AUTO_APPROVAL_ENABLED:
        raise RuntimeError("arbitrary ingress/auto-approval must remain disabled")
    if APPROVAL_REUSE_AFTER_RESTART_ENABLED:
        raise RuntimeError("approval reuse after restart must remain disabled")
    if AUTONOMOUS_RETRY_ENABLED or AUTONOMOUS_MUTATION_ENABLED:
        raise RuntimeError("autonomous retry/mutation must remain disabled")
    if LEASE_STEAL_ENABLED:
        raise RuntimeError("lease stealing must remain disabled")
    if DESTRUCTIVE_EXECUTION_ENABLED:
        raise RuntimeError("destructive execution must remain disabled")
