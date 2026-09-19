from __future__ import annotations

"""AURA Decision Trace v3.

In-memory, privacy-minimized decision tracing for the v3 intelligence stack.

This component records *why* a route decision happened without executing routes,
calling providers, probing hardware, or persisting user content. Raw prompts are
intentionally excluded from the schema. The caller may provide a correlation id
and non-sensitive request metadata.

Typical stages:
- eligibility
- model_policy
- model_switch_gate
- provider_health
- gateway
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

SCHEMA = "aura.decision_trace.v3"
VERSION = "3.0.0"

_ALLOWED_STAGES = {
    "request",
    "eligibility",
    "model_policy",
    "model_switch_gate",
    "provider_health",
    "gateway",
    "completion",
}

_SENSITIVE_KEYS = {
    "prompt",
    "user_text",
    "messages",
    "content",
    "api_key",
    "authorization",
    "token",
    "password",
    "secret",
    "cookie",
    "email_body",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:240]
    return str(value)[:240]


def _sanitize_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Keep only non-sensitive, shallow JSON-like telemetry."""
    if not isinstance(value, Mapping):
        return {}

    out: dict[str, Any] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key or "").strip()
        if not key:
            continue
        folded = key.casefold()
        if folded in _SENSITIVE_KEYS or any(s in folded for s in ("api_key", "password", "secret", "authorization")):
            out[key] = "<redacted>"
            continue

        if isinstance(raw_value, Mapping):
            out[key] = _sanitize_mapping(raw_value)
        elif isinstance(raw_value, (list, tuple)):
            out[key] = [_safe_scalar(v) for v in raw_value[:32]]
        else:
            out[key] = _safe_scalar(raw_value)
    return out


@dataclass(frozen=True)
class DecisionTraceEventV3:
    index: int
    stage: str
    timestamp_utc: str
    outcome: str
    selected_provider: str = ""
    selected_model: str = ""
    reason_codes: tuple[str, ...] = ()
    rejected: tuple[Mapping[str, Any], ...] = ()
    latency_ms: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DecisionTraceSnapshotV3:
    schema: str
    version: str
    trace_id: str
    correlation_id: str
    started_at_utc: str
    completed_at_utc: str | None
    status: str
    request_facts: Mapping[str, Any]
    events: tuple[DecisionTraceEventV3, ...]
    summary: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class DecisionTraceV3:
    """Append-only in-memory trace for one routing/generation decision."""

    def __init__(
        self,
        *,
        correlation_id: str = "",
        task_type: str = "chat",
        mode: str = "automatic",
        privacy: str = "default",
        voice_output: bool = False,
        streaming: bool = True,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self._trace_id = str(uuid4())
        self._correlation_id = str(correlation_id or "")[:160]
        self._started_at_utc = _utc_now()
        self._completed_at_utc: str | None = None
        self._status = "running"
        self._events: list[DecisionTraceEventV3] = []
        self._summary: dict[str, Any] = {}

        self._request_facts = {
            "task_type": str(task_type or "chat")[:80],
            "mode": str(mode or "automatic")[:80],
            "privacy": str(privacy or "default")[:80],
            "voice_output": bool(voice_output),
            "streaming": bool(streaming),
            "metadata": _sanitize_mapping(metadata),
        }

    @property
    def trace_id(self) -> str:
        return self._trace_id

    @property
    def status(self) -> str:
        return self._status

    def add_event(
        self,
        *,
        stage: str,
        outcome: str,
        selected_provider: str = "",
        selected_model: str = "",
        reason_codes: tuple[str, ...] | list[str] = (),
        rejected: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]] = (),
        latency_ms: float | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> DecisionTraceEventV3:
        if self._status != "running":
            raise RuntimeError("cannot append to a completed decision trace")

        normalized_stage = str(stage or "").strip().casefold()
        if normalized_stage not in _ALLOWED_STAGES:
            raise ValueError(f"unsupported trace stage: {stage!r}")

        safe_rejected = []
        for item in list(rejected)[:64]:
            if not isinstance(item, Mapping):
                continue
            safe_rejected.append(_sanitize_mapping(item))

        event = DecisionTraceEventV3(
            index=len(self._events),
            stage=normalized_stage,
            timestamp_utc=_utc_now(),
            outcome=str(outcome or "")[:120],
            selected_provider=str(selected_provider or "")[:80].casefold(),
            selected_model=str(selected_model or "")[:160],
            reason_codes=tuple(
                str(code or "")[:120]
                for code in tuple(reason_codes)[:64]
                if str(code or "").strip()
            ),
            rejected=tuple(safe_rejected),
            latency_ms=(None if latency_ms is None else max(0.0, float(latency_ms))),
            metadata=_sanitize_mapping(metadata),
        )
        self._events.append(event)
        return event

    def complete(
        self,
        *,
        status: str,
        selected_provider: str = "",
        selected_model: str = "",
        finish_reason: str = "",
        fallback_count: int = 0,
        error_chain: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> DecisionTraceSnapshotV3:
        if self._status != "running":
            raise RuntimeError("decision trace already completed")

        safe_errors = []
        for item in list(error_chain)[:32]:
            if isinstance(item, Mapping):
                safe_errors.append(_sanitize_mapping(item))

        self._status = str(status or "completed")[:80].casefold()
        self._completed_at_utc = _utc_now()
        self._summary = {
            "selected_provider": str(selected_provider or "")[:80].casefold(),
            "selected_model": str(selected_model or "")[:160],
            "finish_reason": str(finish_reason or "")[:160],
            "fallback_count": max(0, int(fallback_count or 0)),
            "error_chain": safe_errors,
            "metadata": _sanitize_mapping(metadata),
        }
        return self.snapshot()

    def snapshot(self) -> DecisionTraceSnapshotV3:
        return DecisionTraceSnapshotV3(
            schema=SCHEMA,
            version=VERSION,
            trace_id=self._trace_id,
            correlation_id=self._correlation_id,
            started_at_utc=self._started_at_utc,
            completed_at_utc=self._completed_at_utc,
            status=self._status,
            request_facts=dict(self._request_facts),
            events=tuple(self._events),
            summary=dict(self._summary),
        )
