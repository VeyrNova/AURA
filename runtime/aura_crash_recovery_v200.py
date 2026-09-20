"""AURA A200-R9 R1 cancellation / restart persistence / crash recovery.

R1 repair: every companion crash-journal SQLite connection is now explicitly
closed through a context-managed connection lifetime. This avoids relying on
CPython object finalization for releasing Windows file handles.

MissionEngine remains the canonical mission-state authority.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterator, Mapping

from integrations.pc_control import PC_CONTROL_PROVIDER_ID
from integrations.registry import IntegrationRequest
from mission_engine import MissionEngine, ToolCall
from runtime.aura_supervised_mission_executor_v200 import (
    A200SupervisedMissionExecutor,
    REVERSIBLE_ACTION,
    RESTORE_ACTION,
)


A200_R9_MARKER = "AURA_A200_R9_CANCEL_RESTART_PERSISTENCE_CRASH_RECOVERY_V1"
A200_R9_R1_MARKER = "AURA_A200_R9_R1_SQLITE_HANDLE_LIFECYCLE_REPAIR_V1"

CRASH_JOURNAL_REQUIRED = True
EXPLICIT_SQLITE_CLOSE_REQUIRED = True
AUTO_RESUME_AFTER_CRASH = False
AUTONOMOUS_MUTATION_ENABLED = False
DESTRUCTIVE_EXECUTION_ENABLED = False
CRASH_RECOVERY_ONE_USE = True


class CrashJournalError(RuntimeError):
    pass


class CrashRecoveryError(RuntimeError):
    pass


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


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CrashRecoveryRecord:
    record_id: str
    mission_id: str
    task_id: str
    plan_digest: str
    mutation_receipt_id: str
    recovery_token_id: str
    recovery_digest: str
    recovery: dict[str, Any]
    state: str
    armed_at: str
    restored_at: str | None = None
    restore_receipt_id: str | None = None


@dataclass(frozen=True)
class CrashRecoveryResult:
    mission_id: str
    task_id: str
    record_id: str
    restore_receipt_id: str
    mission_status: str
    restored: bool


class A200CrashRecoveryJournal:
    """Companion SQLite journal with explicit Windows-safe handle lifecycle."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    @contextmanager
    def _session(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except BaseException:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            # R9-R1: never rely on sqlite3.Connection.__del__ for Windows locks.
            conn.close()

    def _ensure_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._session() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS a200_crash_recovery_journal (
                    record_id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    plan_digest TEXT NOT NULL,
                    mutation_receipt_id TEXT NOT NULL,
                    recovery_token_id TEXT NOT NULL,
                    recovery_digest TEXT NOT NULL,
                    recovery_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    armed_at TEXT NOT NULL,
                    restored_at TEXT,
                    restore_receipt_id TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_a200_crash_recovery_mission
                    ON a200_crash_recovery_journal(mission_id, state, armed_at);
                """
            )

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> CrashRecoveryRecord:
        return CrashRecoveryRecord(
            record_id=str(row["record_id"]),
            mission_id=str(row["mission_id"]),
            task_id=str(row["task_id"]),
            plan_digest=str(row["plan_digest"]),
            mutation_receipt_id=str(row["mutation_receipt_id"]),
            recovery_token_id=str(row["recovery_token_id"]),
            recovery_digest=str(row["recovery_digest"]),
            recovery=dict(json.loads(row["recovery_json"])),
            state=str(row["state"]),
            armed_at=str(row["armed_at"]),
            restored_at=None if row["restored_at"] is None else str(row["restored_at"]),
            restore_receipt_id=None if row["restore_receipt_id"] is None else str(row["restore_receipt_id"]),
        )

    def arm(
        self,
        *,
        mission_id: str,
        task_id: str,
        plan_digest: str,
        mutation_receipt_id: str,
        recovery_token_id: str,
        recovery: Mapping[str, Any],
        expected_recovery_digest: str,
    ) -> CrashRecoveryRecord:
        recovery_copy = dict(recovery)
        actual_digest = _digest(recovery_copy)
        if actual_digest != str(expected_recovery_digest):
            raise CrashJournalError("recovery preimage digest mismatch before journal arm")

        pending = self.get_pending(mission_id)
        if pending is not None:
            raise CrashJournalError("mission already owns a pending crash-recovery record")

        seed = {
            "mission_id": mission_id,
            "task_id": task_id,
            "plan_digest": plan_digest,
            "mutation_receipt_id": mutation_receipt_id,
            "recovery_token_id": recovery_token_id,
            "recovery_digest": actual_digest,
        }
        record_id = "a200-crash-" + _digest(seed)[:24]
        armed_at = _utc_now()

        with self._session() as conn:
            conn.execute(
                """
                INSERT INTO a200_crash_recovery_journal(
                    record_id, mission_id, task_id, plan_digest,
                    mutation_receipt_id, recovery_token_id,
                    recovery_digest, recovery_json, state, armed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'armed', ?)
                """,
                (
                    record_id,
                    mission_id,
                    task_id,
                    plan_digest,
                    mutation_receipt_id,
                    recovery_token_id,
                    actual_digest,
                    _canonical_json(recovery_copy),
                    armed_at,
                ),
            )

        record = self.get(record_id)
        if record is None:
            raise CrashJournalError("journal arm did not persist")
        return record

    def get(self, record_id: str) -> CrashRecoveryRecord | None:
        with self._session() as conn:
            row = conn.execute(
                "SELECT * FROM a200_crash_recovery_journal WHERE record_id=?",
                (str(record_id),),
            ).fetchone()
            return None if row is None else self._row_to_record(row)

    def get_pending(self, mission_id: str) -> CrashRecoveryRecord | None:
        with self._session() as conn:
            rows = conn.execute(
                """
                SELECT * FROM a200_crash_recovery_journal
                WHERE mission_id=? AND state='armed'
                ORDER BY armed_at ASC
                """,
                (str(mission_id),),
            ).fetchall()
            if len(rows) > 1:
                raise CrashJournalError("multiple pending crash-recovery records for mission")
            return None if not rows else self._row_to_record(rows[0])

    def mark_restored(self, record_id: str, restore_receipt_id: str) -> CrashRecoveryRecord:
        current = self.get(record_id)
        if current is None:
            raise CrashJournalError("unknown crash-recovery record")
        if current.state != "armed":
            raise CrashJournalError("crash-recovery record already consumed")

        restored_at = _utc_now()
        with self._session() as conn:
            updated = conn.execute(
                """
                UPDATE a200_crash_recovery_journal
                SET state='restored', restored_at=?, restore_receipt_id=?
                WHERE record_id=? AND state='armed'
                """,
                (restored_at, str(restore_receipt_id), str(record_id)),
            ).rowcount
            if updated != 1:
                raise CrashJournalError("crash-recovery one-use transition failed")

        final = self.get(record_id)
        if final is None:
            raise CrashJournalError("restored journal record disappeared")
        return final

    def count(self, *, state: str | None = None) -> int:
        with self._session() as conn:
            if state is None:
                row = conn.execute(
                    "SELECT COUNT(*) AS n FROM a200_crash_recovery_journal"
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) AS n FROM a200_crash_recovery_journal WHERE state=?",
                    (str(state),),
                ).fetchone()
            return int(row["n"])


class A200CrashSafeMissionExecutor(A200SupervisedMissionExecutor):
    """R7 executor plus durable reversible-preimage journaling."""

    def __init__(
        self,
        *,
        mission_engine: MissionEngine,
        read_binding: Any,
        mutation_binding: Any,
        crash_journal: A200CrashRecoveryJournal,
    ) -> None:
        super().__init__(
            mission_engine=mission_engine,
            read_binding=read_binding,
            mutation_binding=mutation_binding,
        )
        self.crash_journal = crash_journal

    def _recovery_preimage_for_token(self, token: Any) -> dict[str, Any]:
        store = getattr(self.mutation_binding, "_recoveries", None)
        if not isinstance(store, dict):
            raise CrashJournalError("R5 recovery store unavailable")
        state = store.get(token.token_id)
        if not isinstance(state, dict):
            raise CrashJournalError("R5 recovery token state missing")
        recovery = state.get("recovery")
        if not isinstance(recovery, Mapping):
            raise CrashJournalError("R5 exact recovery preimage missing")
        recovery_copy = dict(recovery)
        if _digest(recovery_copy) != token.recovery_digest:
            raise CrashJournalError("R5 recovery preimage digest mismatch")
        return recovery_copy

    def tool_executor(self, call: ToolCall) -> dict[str, Any]:
        action = str(call.action or "")

        if action == REVERSIBLE_ACTION:
            result = super().tool_executor(call)
            token = self._recovery_token
            mission_id = self._active_mission_id
            task_id = self._active_task_id
            if token is None or not mission_id or not task_id:
                raise CrashJournalError("mutation returned without active recovery context")

            receipt_id = str(result.get("receipt_id") or "")
            plan_digest = str(result.get("r2_plan_digest") or "")
            if not receipt_id or len(plan_digest) != 64:
                raise CrashJournalError("mutation result lacks receipt/digest for crash journal")

            recovery = self._recovery_preimage_for_token(token)
            record = self.crash_journal.arm(
                mission_id=mission_id,
                task_id=task_id,
                plan_digest=plan_digest,
                mutation_receipt_id=receipt_id,
                recovery_token_id=token.token_id,
                recovery=recovery,
                expected_recovery_digest=token.recovery_digest,
            )
            result = dict(result)
            result["crash_recovery_record_id"] = record.record_id
            result["crash_recovery_state"] = record.state
            return result

        if action == RESTORE_ACTION:
            mission_id = self._active_mission_id
            pending = self.crash_journal.get_pending(mission_id) if mission_id else None
            result = super().tool_executor(call)
            if pending is not None:
                receipt_id = str(result.get("receipt_id") or "")
                if not receipt_id:
                    raise CrashJournalError("planned restore has no receipt id")
                self.crash_journal.mark_restored(pending.record_id, receipt_id)
                result = dict(result)
                result["crash_recovery_record_id"] = pending.record_id
                result["crash_recovery_state"] = "restored"
            return result

        return super().tool_executor(call)

    def _emergency_restore(self, mission_id: str, reason: str) -> str | None:
        pending = self.crash_journal.get_pending(mission_id)
        receipt_id = super()._emergency_restore(mission_id, reason)
        if pending is not None and receipt_id:
            self.crash_journal.mark_restored(pending.record_id, receipt_id)
        return receipt_id

    def recover_after_restart(self, mission_id: str) -> CrashRecoveryResult:
        record = self.crash_journal.get_pending(mission_id)
        if record is None:
            raise CrashRecoveryError("no pending crash-recovery record")

        if _digest(record.recovery) != record.recovery_digest:
            raise CrashRecoveryError("persisted recovery preimage digest mismatch")

        target = record.recovery.get("target")
        if not isinstance(target, Mapping):
            raise CrashRecoveryError("persisted recovery target missing")
        if int(target.get("hwnd") or 0) <= 0:
            raise CrashRecoveryError("persisted recovery HWND invalid")
        if not str(target.get("title") or "").strip():
            raise CrashRecoveryError("persisted recovery title invalid")
        if str(target.get("show_state") or "") not in {"normal", "minimized", "maximized"}:
            raise CrashRecoveryError("persisted recovery show_state invalid")

        request = IntegrationRequest.create(
            provider_id=PC_CONTROL_PROVIDER_ID,
            capability_id=RESTORE_ACTION,
            params=dict(record.recovery),
            origin="a200-r9-crash-recovery",
        )
        result = self.mutation_binding.registry.execute_integration(request)
        if not result.ok or str(result.status) != "succeeded" or not result.receipt_id:
            raise CrashRecoveryError(
                f"canonical crash restore failed status={result.status}"
            )

        self.crash_journal.mark_restored(record.record_id, result.receipt_id)

        mission = self.engine.get_mission(mission_id)
        if record.task_id in mission.tasks:
            self.engine.record_evidence(
                mission_id,
                record.task_id,
                "crash_recovery",
                {
                    "record_id": record.record_id,
                    "mutation_receipt_id": record.mutation_receipt_id,
                    "restore_receipt_id": result.receipt_id,
                    "recovery_digest": record.recovery_digest,
                    "restored": True,
                    "auto_resume_after_crash": False,
                },
            )

        mission = self.engine.get_mission(mission_id)
        if mission.status not in {"completed", "failed", "cancelled"}:
            mission = self.engine.cancel(mission_id)

        return CrashRecoveryResult(
            mission_id=mission_id,
            task_id=record.task_id,
            record_id=record.record_id,
            restore_receipt_id=result.receipt_id,
            mission_status=mission.status,
            restored=True,
        )


def assert_r9_safety_contract() -> None:
    if not CRASH_JOURNAL_REQUIRED:
        raise RuntimeError("crash journal must remain mandatory")
    if not EXPLICIT_SQLITE_CLOSE_REQUIRED:
        raise RuntimeError("explicit SQLite close must remain mandatory")
    if AUTO_RESUME_AFTER_CRASH:
        raise RuntimeError("automatic resume after crash must remain disabled")
    if AUTONOMOUS_MUTATION_ENABLED:
        raise RuntimeError("autonomous mutation must remain disabled")
    if DESTRUCTIVE_EXECUTION_ENABLED:
        raise RuntimeError("destructive execution must remain disabled")
    if not CRASH_RECOVERY_ONE_USE:
        raise RuntimeError("crash recovery must remain one-use")
