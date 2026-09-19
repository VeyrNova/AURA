"""AURA A200-R10 supervised concurrency / locking / idempotency guard.

R10 adds a durable execution-intent ledger around canonical MissionEngine task
identity. It does not replace MissionEngine, IntegrationRegistry, R4/R5, or R9.

Safety contract:
- one active owner per logical mission/task/action key;
- exact request digest binding (changed payload under same logical task fails);
- successful duplicates are suppressed and reuse prior canonical receipt id;
- failed/recovered intents are terminal until a higher supervised gate decides;
- in-progress claims are NEVER auto-stolen after a crash;
- no automatic retry, mutation replay, destructive execution, or shell path.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping


A200_R10_MARKER = "AURA_A200_R10_CONCURRENCY_LOCKING_IDEMPOTENCY_V1"

LEDGER_REQUIRED = True
ONE_ACTIVE_OWNER_PER_KEY = True
DUPLICATE_SUCCESS_REDISPATCH_ENABLED = False
LEASE_STEAL_ENABLED = False
AUTONOMOUS_RETRY_ENABLED = False
AUTONOMOUS_MUTATION_ENABLED = False
DESTRUCTIVE_EXECUTION_ENABLED = False


class ConcurrencyConflict(RuntimeError):
    pass


class IdempotencyConflict(RuntimeError):
    pass


class TerminalIntentError(RuntimeError):
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


def logical_key(
    *,
    mission_id: str,
    task_id: str,
    action: str,
    plan_revision: int,
) -> str:
    payload = {
        "mission_id": str(mission_id),
        "task_id": str(task_id),
        "action": str(action),
        "plan_revision": int(plan_revision),
    }
    return "a200-intent-" + _digest(payload)[:32]


def request_digest(
    *,
    action: str,
    params: Mapping[str, Any] | None,
    plan_digest: str | None,
) -> str:
    return _digest(
        {
            "action": str(action),
            "params": dict(params or {}),
            "plan_digest": None if plan_digest is None else str(plan_digest),
        }
    )


@dataclass(frozen=True)
class IntentRecord:
    intent_key: str
    mission_id: str
    task_id: str
    action: str
    plan_revision: int
    request_digest: str
    state: str
    owner_id: str
    acquired_at: str
    completed_at: str | None
    receipt_id: str | None
    result_json: str | None
    error_digest: str | None
    recovery_receipt_id: str | None


@dataclass(frozen=True)
class ClaimResult:
    disposition: str
    record: IntentRecord


@dataclass(frozen=True)
class GuardedExecutionResult:
    disposition: str
    dispatched: bool
    intent_key: str
    receipt_id: str | None
    result: dict[str, Any] | None


class A200ExecutionIntentLedger:
    """Companion SQLite execution ledger with explicit short-lived connections."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=5.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    @contextmanager
    def _session(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            yield conn
            conn.commit()
        except BaseException:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS a200_execution_intents (
                    intent_key TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    plan_revision INTEGER NOT NULL,
                    request_digest TEXT NOT NULL,
                    state TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    acquired_at TEXT NOT NULL,
                    completed_at TEXT,
                    receipt_id TEXT,
                    result_json TEXT,
                    error_digest TEXT,
                    recovery_receipt_id TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_a200_intent_mission
                    ON a200_execution_intents(mission_id, task_id, state);
                """
            )
        finally:
            conn.close()

    @staticmethod
    def _row(row: sqlite3.Row) -> IntentRecord:
        return IntentRecord(
            intent_key=str(row["intent_key"]),
            mission_id=str(row["mission_id"]),
            task_id=str(row["task_id"]),
            action=str(row["action"]),
            plan_revision=int(row["plan_revision"]),
            request_digest=str(row["request_digest"]),
            state=str(row["state"]),
            owner_id=str(row["owner_id"]),
            acquired_at=str(row["acquired_at"]),
            completed_at=None if row["completed_at"] is None else str(row["completed_at"]),
            receipt_id=None if row["receipt_id"] is None else str(row["receipt_id"]),
            result_json=None if row["result_json"] is None else str(row["result_json"]),
            error_digest=None if row["error_digest"] is None else str(row["error_digest"]),
            recovery_receipt_id=None if row["recovery_receipt_id"] is None else str(row["recovery_receipt_id"]),
        )

    def get(self, intent_key: str) -> IntentRecord | None:
        with self._session() as conn:
            row = conn.execute(
                "SELECT * FROM a200_execution_intents WHERE intent_key=?",
                (str(intent_key),),
            ).fetchone()
            return None if row is None else self._row(row)

    def claim(
        self,
        *,
        intent_key: str,
        mission_id: str,
        task_id: str,
        action: str,
        plan_revision: int,
        request_digest: str,
        owner_id: str,
    ) -> ClaimResult:
        with self._session(immediate=True) as conn:
            row = conn.execute(
                "SELECT * FROM a200_execution_intents WHERE intent_key=?",
                (str(intent_key),),
            ).fetchone()

            if row is None:
                conn.execute(
                    """
                    INSERT INTO a200_execution_intents(
                        intent_key, mission_id, task_id, action, plan_revision,
                        request_digest, state, owner_id, acquired_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'running', ?, ?)
                    """,
                    (
                        str(intent_key),
                        str(mission_id),
                        str(task_id),
                        str(action),
                        int(plan_revision),
                        str(request_digest),
                        str(owner_id),
                        _utc_now(),
                    ),
                )
                fresh = conn.execute(
                    "SELECT * FROM a200_execution_intents WHERE intent_key=?",
                    (str(intent_key),),
                ).fetchone()
                return ClaimResult("acquired", self._row(fresh))

            current = self._row(row)
            if current.request_digest != str(request_digest):
                raise IdempotencyConflict(
                    "logical task already exists with a different exact request digest"
                )

            if current.state == "succeeded":
                return ClaimResult("duplicate_succeeded", current)

            if current.state == "running":
                raise ConcurrencyConflict(
                    f"intent already running under owner {current.owner_id}"
                )

            raise TerminalIntentError(
                f"intent is terminal state={current.state}; automatic replay forbidden"
            )

    def complete_success(
        self,
        *,
        intent_key: str,
        owner_id: str,
        receipt_id: str,
        result: Mapping[str, Any],
    ) -> IntentRecord:
        with self._session(immediate=True) as conn:
            row = conn.execute(
                "SELECT * FROM a200_execution_intents WHERE intent_key=?",
                (str(intent_key),),
            ).fetchone()
            if row is None:
                raise IdempotencyConflict("unknown execution intent")
            current = self._row(row)
            if current.state != "running":
                raise IdempotencyConflict("only running intent may complete")
            if current.owner_id != str(owner_id):
                raise ConcurrencyConflict("owner mismatch on intent completion")
            updated = conn.execute(
                """
                UPDATE a200_execution_intents
                SET state='succeeded', completed_at=?, receipt_id=?, result_json=?
                WHERE intent_key=? AND state='running' AND owner_id=?
                """,
                (
                    _utc_now(),
                    str(receipt_id),
                    _canonical_json(dict(result)),
                    str(intent_key),
                    str(owner_id),
                ),
            ).rowcount
            if updated != 1:
                raise ConcurrencyConflict("atomic intent completion failed")
            final = conn.execute(
                "SELECT * FROM a200_execution_intents WHERE intent_key=?",
                (str(intent_key),),
            ).fetchone()
            return self._row(final)

    def mark_failed(
        self,
        *,
        intent_key: str,
        owner_id: str,
        error: BaseException,
    ) -> IntentRecord:
        err_digest = _digest(
            {
                "type": type(error).__name__,
                "message": str(error),
            }
        )
        with self._session(immediate=True) as conn:
            row = conn.execute(
                "SELECT * FROM a200_execution_intents WHERE intent_key=?",
                (str(intent_key),),
            ).fetchone()
            if row is None:
                raise IdempotencyConflict("unknown execution intent")
            current = self._row(row)
            if current.state != "running" or current.owner_id != str(owner_id):
                raise ConcurrencyConflict("cannot fail intent not owned by caller")
            conn.execute(
                """
                UPDATE a200_execution_intents
                SET state='failed', completed_at=?, error_digest=?
                WHERE intent_key=? AND state='running' AND owner_id=?
                """,
                (_utc_now(), err_digest, str(intent_key), str(owner_id)),
            )
        final = self.get(intent_key)
        if final is None:
            raise IdempotencyConflict("failed intent disappeared")
        return final

    def reconcile_recovered(
        self,
        *,
        intent_key: str,
        request_digest: str,
        recovery_receipt_id: str,
    ) -> IntentRecord:
        with self._session(immediate=True) as conn:
            row = conn.execute(
                "SELECT * FROM a200_execution_intents WHERE intent_key=?",
                (str(intent_key),),
            ).fetchone()
            if row is None:
                raise IdempotencyConflict("unknown execution intent")
            current = self._row(row)
            if current.request_digest != str(request_digest):
                raise IdempotencyConflict("recovery request digest mismatch")
            if current.state != "running":
                raise TerminalIntentError(
                    f"only interrupted running intent may reconcile recovery, got {current.state}"
                )
            conn.execute(
                """
                UPDATE a200_execution_intents
                SET state='recovered', completed_at=?, recovery_receipt_id=?
                WHERE intent_key=? AND state='running'
                """,
                (_utc_now(), str(recovery_receipt_id), str(intent_key)),
            )
        final = self.get(intent_key)
        if final is None:
            raise IdempotencyConflict("recovered intent disappeared")
        return final

    def count(self, *, state: str | None = None) -> int:
        with self._session() as conn:
            if state is None:
                row = conn.execute(
                    "SELECT COUNT(*) AS n FROM a200_execution_intents"
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) AS n FROM a200_execution_intents WHERE state=?",
                    (str(state),),
                ).fetchone()
            return int(row["n"])


class A200IdempotentMissionGuard:
    """Dispatch-once wrapper keyed by canonical MissionEngine mission/task identity."""

    def __init__(self, *, ledger: A200ExecutionIntentLedger) -> None:
        self.ledger = ledger

    def execute_once(
        self,
        *,
        mission_id: str,
        task_id: str,
        action: str,
        params: Mapping[str, Any] | None,
        plan_revision: int,
        plan_digest: str | None,
        owner_id: str,
        dispatch: Callable[[], Mapping[str, Any]],
    ) -> GuardedExecutionResult:
        key = logical_key(
            mission_id=mission_id,
            task_id=task_id,
            action=action,
            plan_revision=plan_revision,
        )
        req_digest = request_digest(
            action=action,
            params=params,
            plan_digest=plan_digest,
        )

        claim = self.ledger.claim(
            intent_key=key,
            mission_id=mission_id,
            task_id=task_id,
            action=action,
            plan_revision=plan_revision,
            request_digest=req_digest,
            owner_id=owner_id,
        )

        if claim.disposition == "duplicate_succeeded":
            cached = (
                None
                if not claim.record.result_json
                else dict(json.loads(claim.record.result_json))
            )
            return GuardedExecutionResult(
                disposition="duplicate_suppressed",
                dispatched=False,
                intent_key=key,
                receipt_id=claim.record.receipt_id,
                result=cached,
            )

        try:
            result = dict(dispatch())
            receipt_id = str(result.get("receipt_id") or "")
            status = str(result.get("status") or "")
            ok = bool(result.get("ok"))
            if not receipt_id or status != "succeeded" or not ok:
                raise IdempotencyConflict(
                    "guarded dispatch must return ok/succeeded with canonical receipt_id"
                )
            self.ledger.complete_success(
                intent_key=key,
                owner_id=owner_id,
                receipt_id=receipt_id,
                result=result,
            )
            return GuardedExecutionResult(
                disposition="executed",
                dispatched=True,
                intent_key=key,
                receipt_id=receipt_id,
                result=result,
            )
        except BaseException as exc:
            current = self.ledger.get(key)
            if current is not None and current.state == "running" and current.owner_id == str(owner_id):
                self.ledger.mark_failed(
                    intent_key=key,
                    owner_id=owner_id,
                    error=exc,
                )
            raise


def assert_r10_safety_contract() -> None:
    if not LEDGER_REQUIRED or not ONE_ACTIVE_OWNER_PER_KEY:
        raise RuntimeError("R10 durable single-owner ledger is mandatory")
    if DUPLICATE_SUCCESS_REDISPATCH_ENABLED:
        raise RuntimeError("successful duplicate redispatch must remain disabled")
    if LEASE_STEAL_ENABLED:
        raise RuntimeError("running-claim lease stealing must remain disabled")
    if AUTONOMOUS_RETRY_ENABLED or AUTONOMOUS_MUTATION_ENABLED:
        raise RuntimeError("autonomous retry/mutation must remain disabled")
    if DESTRUCTIVE_EXECUTION_ENABLED:
        raise RuntimeError("destructive execution must remain disabled")
