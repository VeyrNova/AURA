"""AURA A200-R13 persistent autonomous-PC runtime bootstrap.

R13 turns the already-certified A200 execution chain into one durable runtime
composition without widening permissions.

Canonical chain:
MissionEngine
  -> A200IdempotentCrashSafeMissionExecutor (R11)
  -> A200CrashSafeMissionExecutor (R9/R7)
  -> R4 read binding / R5 reversible binding
  -> IntegrationRegistry
  -> ActionReceiptService
  -> certified W131/W132 Windows provider

Persistence owned by this bootstrap:
- MissionEngine SQLite store
- canonical ActionReceiptStore
- R9 crash-recovery journal
- R10/R11 execution-intent ledger
- R13 supervised-session registry

Startup semantics:
- read-only capability remains available when infrastructure is healthy;
- any durable R9 recovery is reconciled BEFORE mutation readiness;
- a mission found waiting for confirmation is NEVER auto-confirmed;
- ambiguous/nonterminal missions block new mutation until supervised action;
- startup recovery may restore a prior reversible preimage because restoration
  is a safety action, not a new user-requested mutation.

R13 adds no shell, close, terminate, destructive execution, lease stealing,
automatic retry, or autonomous confirmation.
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Callable, Mapping
import uuid

from action_receipts import ActionReceiptService, ActionReceiptStore
from integrations.registry import IntegrationRegistry
from mission_engine import MissionEngine, SQLiteMissionStore, Task, ToolCall
from runtime.aura_crash_recovery_v200 import A200CrashRecoveryJournal
from runtime.aura_execution_idempotency_v200 import A200ExecutionIntentLedger
from runtime.aura_idempotent_mission_executor_v200 import (
    A200IdempotentCrashSafeMissionExecutor,
)
from runtime.aura_pc_control_registry_binding_v131 import (
    register_pc_control_provider_v131,
)
from runtime.aura_readonly_pc_execution_binding_v200 import (
    A200ReadOnlyPcExecutionBinding,
)
from runtime.aura_reversible_mutation_binding_v200 import (
    A200ReversibleMutationBinding,
)
from runtime.integration_permissions_pc_v131 import (
    evaluate_integration_permission_pc_v131,
)


A200_R13_MARKER = "AURA_A200_R13_PERSISTENT_RUNTIME_BOOTSTRAP_STARTUP_RECOVERY_SESSION_BINDING_V1"

DEFAULT_RUNTIME_STATE_ROOT = (
    Path(r"C:\AURA GPT version") / "data" / "a200_runtime"
)

PERSISTENT_RUNTIME_REQUIRED = True
STARTUP_RECOVERY_REQUIRED = True
SUPERVISED_SESSION_BINDING_REQUIRED = True
READ_ONLY_DURING_SUPERVISION_BLOCK = True
AUTO_CONFIRM_ON_STARTUP_ENABLED = False
AUTO_RESUME_NONRECOVERY_MISSIONS_ENABLED = False
AUTONOMOUS_RETRY_ENABLED = False
AUTONOMOUS_MUTATION_ENABLED = False
LEASE_STEAL_ENABLED = False
DESTRUCTIVE_EXECUTION_ENABLED = False


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class RuntimeBootstrapError(RuntimeError):
    pass


class RuntimeMutationBlocked(PermissionError):
    pass


@dataclass(frozen=True)
class StartupRecoveryRecord:
    mission_id: str
    disposition: str
    mission_status_before: str | None
    mission_status_after: str | None
    restore_receipt_id: str | None
    detail: str | None = None


@dataclass(frozen=True)
class RuntimeStartupSnapshot:
    session_id: str
    state_root: str
    read_only_ready: bool
    mutation_ready: bool
    recovered_missions: tuple[str, ...]
    supervision_required: tuple[str, ...]
    startup_failures: tuple[str, ...]
    records: tuple[StartupRecoveryRecord, ...]


class R13SessionStore:
    """Small durable registry used only to find prior supervised missions."""

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

                CREATE TABLE IF NOT EXISTS runtime_sessions (
                    session_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    closed_at TEXT,
                    startup_snapshot_json TEXT
                );

                CREATE TABLE IF NOT EXISTS supervised_missions (
                    mission_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    terminal INTEGER NOT NULL DEFAULT 0,
                    recovery_receipt_id TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_r13_mission_terminal
                ON supervised_missions(terminal, updated_at);
                """
            )

    def create_session(self, *, session_id: str, owner_id: str) -> None:
        now = _utc_now()
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO runtime_sessions(
                    session_id, owner_id, state, started_at
                ) VALUES (?, ?, 'starting', ?)
                """,
                (session_id, owner_id, now),
            )
            conn.commit()

    def set_session_snapshot(
        self,
        *,
        session_id: str,
        state: str,
        snapshot: Mapping[str, Any],
    ) -> None:
        raw = json.dumps(
            dict(snapshot),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                UPDATE runtime_sessions
                   SET state=?, startup_snapshot_json=?
                 WHERE session_id=?
                """,
                (state, raw, session_id),
            )
            conn.commit()

    def close_session(self, *, session_id: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                UPDATE runtime_sessions
                   SET state='closed', closed_at=?
                 WHERE session_id=?
                """,
                (_utc_now(), session_id),
            )
            conn.commit()

    def track_mission(
        self,
        *,
        mission_id: str,
        session_id: str,
        status: str,
        terminal: bool = False,
        recovery_receipt_id: str | None = None,
    ) -> None:
        now = _utc_now()
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO supervised_missions(
                    mission_id, session_id, status, created_at, updated_at,
                    terminal, recovery_receipt_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(mission_id) DO UPDATE SET
                    session_id=excluded.session_id,
                    status=excluded.status,
                    updated_at=excluded.updated_at,
                    terminal=excluded.terminal,
                    recovery_receipt_id=COALESCE(
                        excluded.recovery_receipt_id,
                        supervised_missions.recovery_receipt_id
                    )
                """,
                (
                    mission_id,
                    session_id,
                    status,
                    now,
                    now,
                    1 if terminal else 0,
                    recovery_receipt_id,
                ),
            )
            conn.commit()

    def unfinished_mission_ids(self) -> list[str]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT mission_id
                  FROM supervised_missions
                 WHERE terminal=0
                 ORDER BY created_at, mission_id
                """
            ).fetchall()
        return [str(row["mission_id"]) for row in rows]

    def get_mission_row(self, mission_id: str) -> Mapping[str, Any] | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT *
                  FROM supervised_missions
                 WHERE mission_id=?
                """,
                (mission_id,),
            ).fetchone()
        return None if row is None else dict(row)

    def session_count(self) -> int:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM runtime_sessions"
            ).fetchone()
        return int(row["n"])

    def mission_count(self) -> int:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM supervised_missions"
            ).fetchone()
        return int(row["n"])


class PcRegistrySecurity:
    def authorize(self, action, params, *, user_confirmed=False):
        return evaluate_integration_permission_pc_v131(
            action,
            params=params,
        ).decision


class RuntimeMissionSecurity:
    """MissionEngine still owns confirmation semantics for reversible mutation."""

    def authorize(self, action, params, user_confirmed=False):
        action = str(action or "")
        if action in {
            "pc.discover_windows",
            "pc.discover_processes",
            "pc.get_foreground_window",
            "pc.restore_window_state",
        }:
            return "ALLOW"
        if action in {
            "pc.focus_window",
            "pc.minimize_window",
            "pc.maximize_window",
        }:
            return "ALLOW" if user_confirmed else "REQUIRE_CONFIRMATION"
        return "DENY"


class A200PersistentRuntimeBootstrap:
    def __init__(
        self,
        *,
        state_root: str | Path = DEFAULT_RUNTIME_STATE_ROOT,
        backend: Any = None,
        owner_id: str | None = None,
        after_dispatch_hook: Callable[[ToolCall, dict[str, Any]], None] | None = None,
        perform_startup_recovery: bool = True,
    ) -> None:
        self.state_root = Path(state_root)
        self.state_root.mkdir(parents=True, exist_ok=True)

        self.session_id = "r13_" + uuid.uuid4().hex
        self.owner_id = (
            str(owner_id or "").strip()
            or ("aura-r13-" + self.session_id[-12:])
        )

        self.receipts = ActionReceiptService(
            store=ActionReceiptStore(self.state_root / "receipts.sqlite3")
        )
        self.registry = IntegrationRegistry(
            security_engine=PcRegistrySecurity(),
            receipt_service=self.receipts,
        )
        register_pc_control_provider_v131(self.registry, backend=backend)

        self.read_binding = A200ReadOnlyPcExecutionBinding(
            registry=self.registry,
            origin="a200-r13-runtime-read",
        )
        self.mutation_binding = A200ReversibleMutationBinding(
            registry=self.registry,
            origin="a200-r13-runtime-mutation",
        )

        self.mission_store = SQLiteMissionStore(
            self.state_root / "missions.sqlite3"
        )
        self.crash_journal = A200CrashRecoveryJournal(
            self.state_root / "crash_recovery.sqlite3"
        )
        self.intent_ledger = A200ExecutionIntentLedger(
            self.state_root / "idempotency.sqlite3"
        )
        self.session_store = R13SessionStore(
            self.state_root / "runtime_sessions.sqlite3"
        )

        holder: dict[str, Any] = {}
        self.engine = MissionEngine(
            security_engine=RuntimeMissionSecurity(),
            tool_executor=lambda call: holder["executor"].tool_executor(call),
            store=self.mission_store,
        )
        self.executor = A200IdempotentCrashSafeMissionExecutor(
            mission_engine=self.engine,
            read_binding=self.read_binding,
            mutation_binding=self.mutation_binding,
            crash_journal=self.crash_journal,
            intent_ledger=self.intent_ledger,
            owner_id=self.owner_id,
            after_dispatch_hook=after_dispatch_hook,
        )
        holder["executor"] = self.executor

        self.session_store.create_session(
            session_id=self.session_id,
            owner_id=self.owner_id,
        )

        self._snapshot = RuntimeStartupSnapshot(
            session_id=self.session_id,
            state_root=str(self.state_root),
            read_only_ready=True,
            mutation_ready=False,
            recovered_missions=(),
            supervision_required=(),
            startup_failures=(),
            records=(),
        )

        if perform_startup_recovery:
            self._snapshot = self.reconcile_startup()
        else:
            self._persist_snapshot("starting")

    @property
    def startup_snapshot(self) -> RuntimeStartupSnapshot:
        return self._snapshot

    @property
    def mutation_ready(self) -> bool:
        return bool(self._snapshot.mutation_ready)

    @property
    def read_only_ready(self) -> bool:
        return bool(self._snapshot.read_only_ready)

    def _snapshot_dict(self) -> dict[str, Any]:
        return {
            "session_id": self._snapshot.session_id,
            "state_root": self._snapshot.state_root,
            "read_only_ready": self._snapshot.read_only_ready,
            "mutation_ready": self._snapshot.mutation_ready,
            "recovered_missions": list(self._snapshot.recovered_missions),
            "supervision_required": list(
                self._snapshot.supervision_required
            ),
            "startup_failures": list(self._snapshot.startup_failures),
            "records": [
                {
                    "mission_id": r.mission_id,
                    "disposition": r.disposition,
                    "mission_status_before": r.mission_status_before,
                    "mission_status_after": r.mission_status_after,
                    "restore_receipt_id": r.restore_receipt_id,
                    "detail": r.detail,
                }
                for r in self._snapshot.records
            ],
        }

    def _persist_snapshot(self, state: str) -> None:
        self.session_store.set_session_snapshot(
            session_id=self.session_id,
            state=state,
            snapshot=self._snapshot_dict(),
        )

    @staticmethod
    def _is_terminal_mission_status(status: str) -> bool:
        return str(status or "") in {
            "completed",
            "cancelled",
            "failed",
        }

    def _track_current_mission(
        self,
        mission_id: str,
        *,
        recovery_receipt_id: str | None = None,
    ) -> None:
        mission = self.engine.get_mission(mission_id)
        status = str(mission.status)
        self.session_store.track_mission(
            mission_id=mission_id,
            session_id=self.session_id,
            status=status,
            terminal=self._is_terminal_mission_status(status),
            recovery_receipt_id=recovery_receipt_id,
        )

    def reconcile_startup(self) -> RuntimeStartupSnapshot:
        """Safety-first restart reconciliation; never auto-confirms mutation."""
        recovered: list[str] = []
        supervision: list[str] = []
        failures: list[str] = []
        records: list[StartupRecoveryRecord] = []

        for mission_id in self.session_store.unfinished_mission_ids():
            try:
                mission = self.engine.get_mission(mission_id)
            except Exception as exc:
                failures.append(mission_id)
                records.append(
                    StartupRecoveryRecord(
                        mission_id=mission_id,
                        disposition="mission_load_failed",
                        mission_status_before=None,
                        mission_status_after=None,
                        restore_receipt_id=None,
                        detail=f"{type(exc).__name__}: {exc}",
                    )
                )
                continue

            before = str(mission.status)
            try:
                pending = self.crash_journal.get_pending(mission_id)
            except Exception as exc:
                failures.append(mission_id)
                records.append(
                    StartupRecoveryRecord(
                        mission_id=mission_id,
                        disposition="journal_read_failed",
                        mission_status_before=before,
                        mission_status_after=before,
                        restore_receipt_id=None,
                        detail=f"{type(exc).__name__}: {exc}",
                    )
                )
                continue

            if pending is not None:
                try:
                    result = self.executor.recover_after_restart(
                        mission_id
                    )
                    after = str(self.engine.get_mission(mission_id).status)
                    receipt_id = str(result.restore_receipt_id or "") or None
                    recovered.append(mission_id)
                    self.session_store.track_mission(
                        mission_id=mission_id,
                        session_id=self.session_id,
                        status=after,
                        terminal=True,
                        recovery_receipt_id=receipt_id,
                    )
                    records.append(
                        StartupRecoveryRecord(
                            mission_id=mission_id,
                            disposition="startup_recovered",
                            mission_status_before=before,
                            mission_status_after=after,
                            restore_receipt_id=receipt_id,
                        )
                    )
                except Exception as exc:
                    failures.append(mission_id)
                    records.append(
                        StartupRecoveryRecord(
                            mission_id=mission_id,
                            disposition="startup_recovery_failed",
                            mission_status_before=before,
                            mission_status_after=str(
                                self.engine.get_mission(mission_id).status
                            ),
                            restore_receipt_id=None,
                            detail=f"{type(exc).__name__}: {exc}",
                        )
                    )
                continue

            if self._is_terminal_mission_status(before):
                self.session_store.track_mission(
                    mission_id=mission_id,
                    session_id=self.session_id,
                    status=before,
                    terminal=True,
                )
                records.append(
                    StartupRecoveryRecord(
                        mission_id=mission_id,
                        disposition="terminal_reconciled",
                        mission_status_before=before,
                        mission_status_after=before,
                        restore_receipt_id=None,
                    )
                )
                continue

            # Waiting confirmation, running-without-journal, planned, recovering,
            # or any unknown nonterminal state is supervisory work. No auto resume.
            supervision.append(mission_id)
            self.session_store.track_mission(
                mission_id=mission_id,
                session_id=self.session_id,
                status=before,
                terminal=False,
            )
            records.append(
                StartupRecoveryRecord(
                    mission_id=mission_id,
                    disposition="supervision_required",
                    mission_status_before=before,
                    mission_status_after=before,
                    restore_receipt_id=None,
                )
            )

        self._snapshot = RuntimeStartupSnapshot(
            session_id=self.session_id,
            state_root=str(self.state_root),
            read_only_ready=(len(failures) == 0),
            mutation_ready=(
                len(failures) == 0
                and len(supervision) == 0
            ),
            recovered_missions=tuple(recovered),
            supervision_required=tuple(supervision),
            startup_failures=tuple(failures),
            records=tuple(records),
        )
        self._persist_snapshot(
            "ready" if self._snapshot.mutation_ready else "supervision_required"
        )
        return self._snapshot

    def refresh_readiness(self) -> RuntimeStartupSnapshot:
        """Re-evaluate tracked mission states without auto executing work."""
        recovered = list(self._snapshot.recovered_missions)
        failures = list(self._snapshot.startup_failures)
        supervision: list[str] = []
        records = list(self._snapshot.records)

        for mission_id in self.session_store.unfinished_mission_ids():
            try:
                mission = self.engine.get_mission(mission_id)
                status = str(mission.status)
                pending = self.crash_journal.get_pending(mission_id)
                if pending is not None:
                    supervision.append(mission_id)
                elif self._is_terminal_mission_status(status):
                    self.session_store.track_mission(
                        mission_id=mission_id,
                        session_id=self.session_id,
                        status=status,
                        terminal=True,
                    )
                else:
                    supervision.append(mission_id)
            except Exception:
                failures.append(mission_id)

        self._snapshot = RuntimeStartupSnapshot(
            session_id=self.session_id,
            state_root=str(self.state_root),
            read_only_ready=(len(failures) == 0),
            mutation_ready=(
                len(failures) == 0
                and len(supervision) == 0
            ),
            recovered_missions=tuple(dict.fromkeys(recovered)),
            supervision_required=tuple(dict.fromkeys(supervision)),
            startup_failures=tuple(dict.fromkeys(failures)),
            records=tuple(records),
        )
        self._persist_snapshot(
            "ready" if self._snapshot.mutation_ready else "supervision_required"
        )
        return self._snapshot

    def execute_read_only(
        self,
        capability_id: str,
        *,
        params: Mapping[str, Any] | None = None,
        step_id: str = "r13-runtime-read",
    ) -> Any:
        if not self.read_only_ready:
            raise RuntimeBootstrapError(
                "read-only runtime unavailable because startup reconciliation failed"
            )
        capability = str(capability_id or "")
        if capability not in {
            "pc.discover_windows",
            "pc.discover_processes",
            "pc.get_foreground_window",
        }:
            raise RuntimeBootstrapError(
                "R13 execute_read_only accepts only the certified R4 read allowlist"
            )
        return self.read_binding.execute_capability(
            capability,
            params=dict(params or {}),
            step_id=step_id,
        )

    def create_supervised_window_mission(
        self,
        *,
        hwnd: int,
        title: str,
        goal: str = "A200-R13 supervised reversible window mission",
    ) -> str:
        if not self.mutation_ready:
            raise RuntimeMutationBlocked(
                "new mutation mission blocked until startup supervision is clear"
            )
        mission = self.engine.create_mission(goal)
        self.engine.plan_mission(
            mission.mission_id,
            self.executor.build_mission_task_specs(
                hwnd=int(hwnd),
                title=str(title),
            ),
        )
        self.engine.start_mission(mission.mission_id)
        self._track_current_mission(mission.mission_id)
        self.refresh_readiness()
        return mission.mission_id

    def run_tracked_until_pause_or_complete(self, mission_id: str) -> Any:
        row = self.session_store.get_mission_row(mission_id)
        if row is None:
            raise RuntimeBootstrapError("mission is not bound to R13 session registry")
        result = self.executor.run_until_pause_or_complete(mission_id)
        self._track_current_mission(mission_id)
        self.refresh_readiness()
        return result

    def explicitly_confirm_tracked_mission(
        self,
        mission_id: str,
        *,
        explicit_confirmation: bool,
    ) -> Any:
        if explicit_confirmation is not True:
            raise RuntimeMutationBlocked(
                "explicit confirmation token required for reversible mutation"
            )
        row = self.session_store.get_mission_row(mission_id)
        if row is None:
            raise RuntimeBootstrapError("mission is not bound to R13 session registry")

        mission = self.engine.get_mission(mission_id)
        waiting = [
            task
            for task in mission.tasks.values()
            if str(task.status) == "waiting_confirmation"
        ]
        if len(waiting) != 1:
            raise RuntimeMutationBlocked(
                "exactly one waiting_confirmation task required"
            )

        task = self.executor.confirm_waiting_task(mission_id)
        self._track_current_mission(mission_id)

        if str(task.status) != "succeeded":
            self.refresh_readiness()
            return task

        result = self.executor.run_until_pause_or_complete(mission_id)
        self._track_current_mission(mission_id)
        self.refresh_readiness()
        return result

    def close(self) -> None:
        self._persist_snapshot("closing")
        self.session_store.close_session(session_id=self.session_id)


def assert_r13_safety_contract() -> None:
    if not PERSISTENT_RUNTIME_REQUIRED:
        raise RuntimeError("R13 persistent runtime must remain mandatory")
    if not STARTUP_RECOVERY_REQUIRED:
        raise RuntimeError("startup recovery must remain mandatory")
    if not SUPERVISED_SESSION_BINDING_REQUIRED:
        raise RuntimeError("supervised session binding must remain mandatory")
    if not READ_ONLY_DURING_SUPERVISION_BLOCK:
        raise RuntimeError("safe read-only access should remain available")
    if AUTO_CONFIRM_ON_STARTUP_ENABLED:
        raise RuntimeError("startup auto-confirm must remain disabled")
    if AUTO_RESUME_NONRECOVERY_MISSIONS_ENABLED:
        raise RuntimeError("non-recovery auto-resume must remain disabled")
    if AUTONOMOUS_RETRY_ENABLED or AUTONOMOUS_MUTATION_ENABLED:
        raise RuntimeError("autonomous retry/mutation must remain disabled")
    if LEASE_STEAL_ENABLED:
        raise RuntimeError("lease stealing must remain disabled")
    if DESTRUCTIVE_EXECUTION_ENABLED:
        raise RuntimeError("destructive execution must remain disabled")
