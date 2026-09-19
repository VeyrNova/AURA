"""AURA v0.8.9 Action Receipts + Capability Context.

Structured traceability for actionable operations without replacing
MissionEngine task evidence or SecurityPolicyEngine authorization.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from contextlib import closing
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence


RECEIPT_STATUSES = (
    "requested",
    "waiting_confirmation",
    "denied",
    "running",
    "succeeded",
    "failed",
    "cancelled",
)

TERMINAL_RECEIPT_STATUSES = {"denied", "succeeded", "failed", "cancelled"}
SENSITIVE_KEYS = {
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "authorization", "cookie", "session", "credential", "credentials",
    "private_key", "access_key", "refresh_token",
}

ALLOW = "ALLOW"
DENY = "DENY"
REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"


class ActionReceiptError(RuntimeError):
    pass


class ReceiptStateError(ActionReceiptError):
    pass


class CapabilityError(ActionReceiptError):
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


def _stable_id(prefix: str, *parts: Any) -> str:
    return prefix + hashlib.sha256(
        _canonical_json(parts).encode("utf-8")
    ).hexdigest()[:24]


def _normalize_decision(value: Any) -> str:
    if value is None:
        return DENY
    candidates = (
        getattr(value, "name", None),
        getattr(value, "value", None),
        value,
    )
    for candidate in candidates:
        if candidate is None:
            continue
        text = str(candidate).upper().strip()
        for expected in (ALLOW, DENY, REQUIRE_CONFIRMATION):
            if text == expected or text.endswith("." + expected):
                return expected
    return DENY


def _redact(value: Any, key: str = "") -> Any:
    if str(key).casefold() in SENSITIVE_KEYS:
        return "<redacted>"

    if isinstance(value, Mapping):
        return {
            str(k): _redact(v, str(k))
            for k, v in sorted(value.items(), key=lambda item: str(item[0]))
        }

    if isinstance(value, (list, tuple, set)):
        return [_redact(v) for v in value]

    if isinstance(value, bytes):
        return "<bytes:" + str(len(value)) + ">"

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    return str(value)


def digest_payload(value: Any) -> str:
    redacted = _redact(value)
    return hashlib.sha256(
        _canonical_json(redacted).encode("utf-8")
    ).hexdigest()


def _safe_error_text(value: Any, limit: int = 400) -> str:
    text = str(value or "")
    for key in SENSITIVE_KEYS:
        text = text.replace(key, "<sensitive-key>")
    if len(text) > limit:
        text = text[:limit] + "..."
    return text


@dataclass(frozen=True)
class CapabilityContext:
    capability_id: str
    provider: str
    available: bool
    permission_state: str
    risk_tier: str
    requires_confirmation: bool
    side_effect_class: str
    evidence_required: bool
    health_state: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ActionReceipt:
    receipt_id: str
    mission_id: Optional[str]
    task_id: Optional[str]
    action: str
    tool_name: str
    capability_id: str
    origin: str
    policy_decision: Optional[str]
    confirmation_state: str
    requested_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    status: str
    params_digest: str
    result_digest: Optional[str]
    evidence_refs: list[str] = field(default_factory=list)
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    attempt: int = 1
    capability_context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "action": self.action,
            "tool_name": self.tool_name,
            "capability_id": self.capability_id,
            "origin": self.origin,
            "policy_decision": self.policy_decision,
            "confirmation_state": self.confirmation_state,
            "requested_at": self.requested_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "params_digest": self.params_digest,
            "result_digest": self.result_digest,
            "evidence_refs": list(self.evidence_refs),
            "error": self.error,
            "duration_ms": self.duration_ms,
            "attempt": self.attempt,
            "capability_context": dict(self.capability_context),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ActionReceipt":
        return cls(
            receipt_id=str(value["receipt_id"]),
            mission_id=value.get("mission_id"),
            task_id=value.get("task_id"),
            action=str(value["action"]),
            tool_name=str(value["tool_name"]),
            capability_id=str(value["capability_id"]),
            origin=str(value["origin"]),
            policy_decision=value.get("policy_decision"),
            confirmation_state=str(value.get("confirmation_state", "not_required")),
            requested_at=str(value["requested_at"]),
            started_at=value.get("started_at"),
            completed_at=value.get("completed_at"),
            status=str(value["status"]),
            params_digest=str(value["params_digest"]),
            result_digest=value.get("result_digest"),
            evidence_refs=list(value.get("evidence_refs") or []),
            error=value.get("error"),
            duration_ms=value.get("duration_ms"),
            attempt=int(value.get("attempt", 1)),
            capability_context=dict(value.get("capability_context") or {}),
        )


@dataclass(frozen=True)
class ActionReceiptEvent:
    event_id: str
    receipt_id: str
    sequence: int
    event_type: str
    payload_digest: str
    created_at: str


class ActionReceiptStore:
    """Companion SQLite persistence for action receipts."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS action_receipts (
                    receipt_id TEXT PRIMARY KEY,
                    origin TEXT NOT NULL,
                    mission_id TEXT,
                    task_id TEXT,
                    action TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    capability_id TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_action_receipts_task
                    ON action_receipts(mission_id, task_id, action, attempt);

                CREATE INDEX IF NOT EXISTS idx_action_receipts_origin
                    ON action_receipts(origin, action, requested_at);

                CREATE TABLE IF NOT EXISTS action_receipt_events (
                    event_id TEXT PRIMARY KEY,
                    receipt_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_digest TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_receipt_event_sequence
                    ON action_receipt_events(receipt_id, sequence);
                """
            )

    def save(self, receipt: ActionReceipt) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO action_receipts(
                    receipt_id, origin, mission_id, task_id, action, tool_name,
                    capability_id, attempt, status, requested_at,
                    snapshot_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(receipt_id) DO UPDATE SET
                    status=excluded.status,
                    snapshot_json=excluded.snapshot_json,
                    updated_at=excluded.updated_at
                """,
                (
                    receipt.receipt_id,
                    receipt.origin,
                    receipt.mission_id,
                    receipt.task_id,
                    receipt.action,
                    receipt.tool_name,
                    receipt.capability_id,
                    receipt.attempt,
                    receipt.status,
                    receipt.requested_at,
                    _canonical_json(receipt.to_dict()),
                    _utc_now(),
                ),
            )

    def append_event(
        self,
        receipt_id: str,
        sequence: int,
        event_type: str,
        payload: Mapping[str, Any],
    ) -> ActionReceiptEvent:
        created_at = _utc_now()
        payload_digest = digest_payload(payload)
        event_id = _stable_id(
            "rce_",
            receipt_id,
            sequence,
            event_type,
            payload_digest,
        )
        event = ActionReceiptEvent(
            event_id=event_id,
            receipt_id=receipt_id,
            sequence=sequence,
            event_type=event_type,
            payload_digest=payload_digest,
            created_at=created_at,
        )
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO action_receipt_events(
                    event_id, receipt_id, sequence, event_type,
                    payload_digest, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.receipt_id,
                    event.sequence,
                    event.event_type,
                    event.payload_digest,
                    event.created_at,
                ),
            )
        return event

    def load(self, receipt_id: str) -> Optional[ActionReceipt]:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT snapshot_json FROM action_receipts WHERE receipt_id=?",
                (receipt_id,),
            ).fetchone()
        if row is None:
            return None
        return ActionReceipt.from_dict(json.loads(row["snapshot_json"]))

    def list_receipts(self) -> list[ActionReceipt]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT snapshot_json
                FROM action_receipts
                ORDER BY rowid ASC
                """
            ).fetchall()
        return [ActionReceipt.from_dict(json.loads(row["snapshot_json"])) for row in rows]

    def count(self) -> int:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM action_receipts").fetchone()
        return int(row["n"])

    def next_attempt(
        self,
        *,
        origin: str,
        mission_id: Optional[str],
        task_id: Optional[str],
        action: str,
    ) -> int:
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT COALESCE(MAX(attempt), 0) AS n
                FROM action_receipts
                WHERE origin=?
                  AND ((mission_id IS NULL AND ? IS NULL) OR mission_id=?)
                  AND ((task_id IS NULL AND ? IS NULL) OR task_id=?)
                  AND action=?
                """,
                (
                    origin,
                    mission_id,
                    mission_id,
                    task_id,
                    task_id,
                    action,
                ),
            ).fetchone()
        return int(row["n"]) + 1

    def event_count(self, receipt_id: str) -> int:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM action_receipt_events WHERE receipt_id=?",
                (receipt_id,),
            ).fetchone()
        return int(row["n"])


class CapabilityRegistry:
    """Runtime capability snapshot resolver."""

    def __init__(self):
        self._contexts: dict[str, CapabilityContext] = {}

    def register(self, context: CapabilityContext) -> CapabilityContext:
        self._contexts[context.capability_id] = context
        return context

    def resolve_capability(
        self,
        capability_id: str,
        *,
        provider: str = "unknown",
    ) -> CapabilityContext:
        capability_id = str(capability_id).strip()
        if capability_id in self._contexts:
            return self._contexts[capability_id]

        return CapabilityContext(
            capability_id=capability_id or "unknown",
            provider=str(provider or "unknown"),
            available=False,
            permission_state="unknown",
            risk_tier="unknown",
            requires_confirmation=True,
            side_effect_class="unknown",
            evidence_required=True,
            health_state="unknown",
        )

    def build_capability_context(
        self,
        *,
        capability_id: str,
        provider: str,
        available: bool,
        permission_state: str,
        risk_tier: str,
        requires_confirmation: bool,
        side_effect_class: str,
        evidence_required: bool,
        health_state: str,
    ) -> CapabilityContext:
        return CapabilityContext(
            capability_id=str(capability_id),
            provider=str(provider),
            available=bool(available),
            permission_state=str(permission_state),
            risk_tier=str(risk_tier),
            requires_confirmation=bool(requires_confirmation),
            side_effect_class=str(side_effect_class),
            evidence_required=bool(evidence_required),
            health_state=str(health_state),
        )


class ActionReceiptService:
    """Canonical action-receipt lifecycle authority."""

    def __init__(
        self,
        *,
        store: ActionReceiptStore,
        capability_registry: Optional[CapabilityRegistry] = None,
    ):
        self.store = store
        self.capability_registry = capability_registry or CapabilityRegistry()
        self._events: dict[str, int] = {}
        self._started_monotonic: dict[str, float] = {}

    def build_capability_context(self, **kwargs: Any) -> CapabilityContext:
        return self.capability_registry.build_capability_context(**kwargs)

    def resolve_capability(
        self,
        capability_id: str,
        *,
        provider: str = "unknown",
    ) -> CapabilityContext:
        return self.capability_registry.resolve_capability(
            capability_id,
            provider=provider,
        )

    def _receipt(self, receipt_id: str) -> ActionReceipt:
        receipt = self.store.load(receipt_id)
        if receipt is None:
            raise KeyError(receipt_id)
        return receipt

    def _assert_mutable(self, receipt: ActionReceipt) -> None:
        if receipt.status in TERMINAL_RECEIPT_STATUSES:
            raise ReceiptStateError(
                "terminal receipt is immutable: " + receipt.status
            )

    def _event(
        self,
        receipt: ActionReceipt,
        event_type: str,
        payload: Mapping[str, Any],
    ) -> None:
        sequence = self._events.get(receipt.receipt_id)
        if sequence is None:
            sequence = self.store.event_count(receipt.receipt_id)
        sequence += 1
        self._events[receipt.receipt_id] = sequence
        self.store.append_event(
            receipt.receipt_id,
            sequence,
            event_type,
            payload,
        )

    def begin_receipt(
        self,
        *,
        action: str,
        tool_name: str,
        capability_context: CapabilityContext,
        origin: str,
        params: Optional[Mapping[str, Any]] = None,
        mission_id: Optional[str] = None,
        task_id: Optional[str] = None,
        attempt: Optional[int] = None,
    ) -> ActionReceipt:
        action = str(action).strip()
        tool_name = str(tool_name).strip()
        origin = str(origin).strip()
        if not action or not tool_name or not origin:
            raise ValueError("action, tool_name and origin are required")

        if attempt is None:
            attempt = self.store.next_attempt(
                origin=origin,
                mission_id=mission_id,
                task_id=task_id,
                action=action,
            )

        params_digest = digest_payload(dict(params or {}))
        receipt_id = _stable_id(
            "rcp_",
            origin,
            mission_id,
            task_id,
            action,
            tool_name,
            capability_context.capability_id,
            int(attempt),
            params_digest,
        )

        existing = self.store.load(receipt_id)
        if existing is not None:
            return existing

        receipt = ActionReceipt(
            receipt_id=receipt_id,
            mission_id=mission_id,
            task_id=task_id,
            action=action,
            tool_name=tool_name,
            capability_id=capability_context.capability_id,
            origin=origin,
            policy_decision=None,
            confirmation_state=(
                "required"
                if capability_context.requires_confirmation
                else "not_required"
            ),
            requested_at=_utc_now(),
            started_at=None,
            completed_at=None,
            status="requested",
            params_digest=params_digest,
            result_digest=None,
            evidence_refs=[],
            error=None,
            duration_ms=None,
            attempt=int(attempt),
            capability_context=capability_context.to_dict(),
        )
        self.store.save(receipt)
        self._event(
            receipt,
            "receipt_requested",
            {
                "status": receipt.status,
                "params_digest": receipt.params_digest,
                "capability_id": receipt.capability_id,
            },
        )
        return receipt

    def record_receipt(self, receipt: ActionReceipt) -> ActionReceipt:
        self.store.save(receipt)
        return receipt

    def record_policy_decision(
        self,
        receipt_id: str,
        decision: Any,
        *,
        user_confirmed: bool = False,
    ) -> ActionReceipt:
        receipt = self._receipt(receipt_id)
        self._assert_mutable(receipt)

        normalized = _normalize_decision(decision)
        receipt.policy_decision = normalized

        if normalized == REQUIRE_CONFIRMATION:
            receipt.status = "waiting_confirmation"
            receipt.confirmation_state = "pending"
            self.store.save(receipt)
            self._event(
                receipt,
                "policy_waiting_confirmation",
                {
                    "decision": normalized,
                    "user_confirmed": bool(user_confirmed),
                },
            )
            return receipt

        if normalized == DENY:
            receipt.status = "denied"
            receipt.confirmation_state = (
                "rejected" if user_confirmed else receipt.confirmation_state
            )
            receipt.completed_at = _utc_now()
            receipt.duration_ms = 0
            self.store.save(receipt)
            self._event(
                receipt,
                "policy_denied",
                {
                    "decision": normalized,
                    "user_confirmed": bool(user_confirmed),
                },
            )
            return receipt

        if user_confirmed:
            receipt.confirmation_state = "confirmed"
        elif receipt.confirmation_state == "pending":
            receipt.confirmation_state = "confirmed"

        receipt.status = "requested"
        self.store.save(receipt)
        self._event(
            receipt,
            "policy_allowed",
            {
                "decision": normalized,
                "user_confirmed": bool(user_confirmed),
            },
        )
        return receipt

    def mark_running(self, receipt_id: str) -> ActionReceipt:
        receipt = self._receipt(receipt_id)
        self._assert_mutable(receipt)
        if receipt.policy_decision != ALLOW:
            raise ReceiptStateError("receipt cannot run without ALLOW")

        receipt.status = "running"
        receipt.started_at = receipt.started_at or _utc_now()
        self._started_monotonic.setdefault(receipt_id, time.perf_counter())
        self.store.save(receipt)
        self._event(receipt, "execution_started", {"status": "running"})
        return receipt

    def _duration_ms(self, receipt: ActionReceipt) -> int:
        start = self._started_monotonic.pop(receipt.receipt_id, None)
        if start is not None:
            return max(0, int((time.perf_counter() - start) * 1000))
        return 0

    def complete_receipt(
        self,
        receipt_id: str,
        *,
        result: Any,
        evidence_refs: Sequence[str] = (),
    ) -> ActionReceipt:
        receipt = self._receipt(receipt_id)
        self._assert_mutable(receipt)
        if receipt.status != "running":
            raise ReceiptStateError("receipt is not running")

        receipt.result_digest = digest_payload(result)
        receipt.evidence_refs = sorted(
            set(str(x) for x in evidence_refs if str(x))
        )
        receipt.completed_at = _utc_now()
        receipt.duration_ms = self._duration_ms(receipt)
        receipt.status = "succeeded"
        self.store.save(receipt)
        self._event(
            receipt,
            "execution_succeeded",
            {
                "result_digest": receipt.result_digest,
                "evidence_refs": receipt.evidence_refs,
                "duration_ms": receipt.duration_ms,
            },
        )
        return receipt

    def fail_receipt(
        self,
        receipt_id: str,
        *,
        error: Any,
        result: Any = None,
        evidence_refs: Sequence[str] = (),
    ) -> ActionReceipt:
        receipt = self._receipt(receipt_id)
        self._assert_mutable(receipt)

        receipt.result_digest = (
            digest_payload(result) if result is not None else None
        )
        receipt.evidence_refs = sorted(
            set(str(x) for x in evidence_refs if str(x))
        )
        receipt.error = _safe_error_text(error)
        receipt.completed_at = _utc_now()
        receipt.duration_ms = self._duration_ms(receipt)
        receipt.status = "failed"
        self.store.save(receipt)
        self._event(
            receipt,
            "execution_failed",
            {
                "error_digest": digest_payload(receipt.error),
                "evidence_refs": receipt.evidence_refs,
                "duration_ms": receipt.duration_ms,
            },
        )
        return receipt

    def cancel_receipt(
        self,
        receipt_id: str,
        *,
        reason: str = "cancelled",
    ) -> ActionReceipt:
        receipt = self._receipt(receipt_id)
        self._assert_mutable(receipt)

        receipt.error = _safe_error_text(reason)
        receipt.completed_at = _utc_now()
        receipt.duration_ms = self._duration_ms(receipt)
        receipt.status = "cancelled"
        self.store.save(receipt)
        self._event(
            receipt,
            "receipt_cancelled",
            {"reason_digest": digest_payload(reason)},
        )
        return receipt

    def get_receipt(self, receipt_id: str) -> ActionReceipt:
        return self._receipt(receipt_id)

    def list_receipts(self) -> list[ActionReceipt]:
        return self.store.list_receipts()

    def execute_action(
        self,
        *,
        action: str,
        tool_name: str,
        capability_context: CapabilityContext,
        origin: str,
        params: Mapping[str, Any],
        security_engine: Any,
        executor: Callable[[str, Mapping[str, Any]], Any],
        user_confirmed: bool = False,
    ) -> ActionReceipt:
        receipt = self.begin_receipt(
            action=action,
            tool_name=tool_name,
            capability_context=capability_context,
            origin=origin,
            params=params,
        )

        decision = _call_authorize(
            security_engine,
            action,
            params,
            user_confirmed=user_confirmed,
        )
        receipt = self.record_policy_decision(
            receipt.receipt_id,
            decision,
            user_confirmed=user_confirmed,
        )

        if receipt.status in {"denied", "waiting_confirmation"}:
            return receipt

        self.mark_running(receipt.receipt_id)
        try:
            result = executor(action, params)
        except Exception as exc:
            return self.fail_receipt(
                receipt.receipt_id,
                error=exc,
            )

        return self.complete_receipt(
            receipt.receipt_id,
            result=result,
        )


def _call_authorize(
    security_engine: Any,
    action: str,
    params: Mapping[str, Any],
    *,
    user_confirmed: bool,
) -> Any:
    authorize = getattr(security_engine, "authorize", None)
    if not callable(authorize):
        return DENY

    try:
        return authorize(
            action,
            dict(params),
            user_confirmed=user_confirmed,
        )
    except TypeError:
        try:
            return authorize(action, dict(params))
        except Exception:
            return DENY
    except Exception:
        return DENY


class ActionReceiptMissionAdapter:
    """Receipt adapter around an existing MissionEngine instance.

    The adapter replaces only the injected security/tool callables on the
    instance. MissionEngine remains the orchestration authority.
    """

    def __init__(
        self,
        *,
        mission_engine: Any,
        receipt_service: ActionReceiptService,
        capability_registry: CapabilityRegistry,
    ):
        self.mission_engine = mission_engine
        self.receipt_service = receipt_service
        self.capability_registry = capability_registry

        self._base_security = mission_engine.security_engine
        self._base_executor = mission_engine.tool_executor
        self._local = threading.local()
        self._pending_receipt_by_task: dict[tuple[str, str], str] = {}

        mission_engine.security_engine = _ReceiptedSecurityProxy(self)
        mission_engine.tool_executor = _ReceiptedToolProxy(self)

    def _active(self) -> dict[str, Any]:
        active = getattr(self._local, "active", None)
        if active is None:
            raise ReceiptStateError("no active mission receipt context")
        return active

    def execute_task(
        self,
        mission_id: str,
        task_id: str,
        *,
        user_confirmed: bool = False,
    ) -> Any:
        mission = self.mission_engine.get_mission(mission_id)
        task = mission.tasks[task_id]
        pending_key = (mission_id, task_id)

        receipt = None
        pending_id = self._pending_receipt_by_task.get(pending_key)
        if pending_id:
            candidate = self.receipt_service.get_receipt(pending_id)
            if candidate.status == "waiting_confirmation":
                receipt = candidate

        if receipt is None:
            capability = self.capability_registry.resolve_capability(
                task.tool_call.tool_name,
                provider=task.tool_call.tool_name,
            )
            receipt = self.receipt_service.begin_receipt(
                action=task.tool_call.action,
                tool_name=task.tool_call.tool_name,
                capability_context=capability,
                origin="MissionEngine",
                params=task.tool_call.params,
                mission_id=mission_id,
                task_id=task_id,
            )

        active = {
            "receipt_id": receipt.receipt_id,
            "mission_id": mission_id,
            "task_id": task_id,
            "user_confirmed": bool(user_confirmed),
            "tool_result": None,
            "tool_error": None,
        }
        self._local.active = active

        try:
            updated_task = self.mission_engine.execute_task(
                mission_id,
                task_id,
                user_confirmed=user_confirmed,
            )

            current = self.receipt_service.get_receipt(receipt.receipt_id)

            if updated_task.status == "waiting_confirmation":
                self._pending_receipt_by_task[pending_key] = receipt.receipt_id
                return updated_task

            self._pending_receipt_by_task.pop(pending_key, None)

            evidence_refs = list(updated_task.evidence_ids)

            if updated_task.status == "succeeded":
                current = self.receipt_service.get_receipt(receipt.receipt_id)
                if current.status == "running":
                    self.receipt_service.complete_receipt(
                        receipt.receipt_id,
                        result=updated_task.result,
                        evidence_refs=evidence_refs,
                    )
                return updated_task

            if updated_task.status == "failed":
                current = self.receipt_service.get_receipt(receipt.receipt_id)
                if current.status not in TERMINAL_RECEIPT_STATUSES:
                    self.receipt_service.fail_receipt(
                        receipt.receipt_id,
                        error=updated_task.error or "mission task failed",
                        result=updated_task.result,
                        evidence_refs=evidence_refs,
                    )
                return updated_task

            if updated_task.status == "cancelled":
                current = self.receipt_service.get_receipt(receipt.receipt_id)
                if current.status not in TERMINAL_RECEIPT_STATUSES:
                    self.receipt_service.cancel_receipt(
                        receipt.receipt_id,
                        reason="mission task cancelled",
                    )
                return updated_task

            return updated_task
        finally:
            self._local.active = None


class _ReceiptedSecurityProxy:
    def __init__(self, adapter: ActionReceiptMissionAdapter):
        self.adapter = adapter

    def authorize(
        self,
        action: str,
        params: Mapping[str, Any],
        user_confirmed: bool = False,
    ) -> Any:
        active = self.adapter._active()
        raw = _call_authorize(
            self.adapter._base_security,
            action,
            params,
            user_confirmed=user_confirmed,
        )
        self.adapter.receipt_service.record_policy_decision(
            active["receipt_id"],
            raw,
            user_confirmed=user_confirmed,
        )
        return raw


class _ReceiptedToolProxy:
    def __init__(self, adapter: ActionReceiptMissionAdapter):
        self.adapter = adapter

    def __call__(self, tool_call: Any) -> Any:
        active = self.adapter._active()
        self.adapter.receipt_service.mark_running(active["receipt_id"])
        try:
            result = self.adapter._base_executor(tool_call)
        except Exception as exc:
            active["tool_error"] = exc
            raise
        active["tool_result"] = result
        return result


__all__ = [
    "RECEIPT_STATUSES",
    "TERMINAL_RECEIPT_STATUSES",
    "ActionReceiptError",
    "ReceiptStateError",
    "CapabilityError",
    "CapabilityContext",
    "ActionReceipt",
    "ActionReceiptEvent",
    "ActionReceiptStore",
    "CapabilityRegistry",
    "ActionReceiptService",
    "ActionReceiptMissionAdapter",
    "digest_payload",
]
