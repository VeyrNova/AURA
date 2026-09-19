from __future__ import annotations

"""AURA Provider Health Registry v3.

In-memory provider health state machine for the future Intelligence Gateway.

This component does NOT call providers, perform HTTP requests, select models,
rank providers, or persist secrets. Provider adapters/gateway report outcomes
into the registry; the registry returns neutral health/eligibility facts.

States:
- unknown
- healthy
- degraded
- rate_limited
- cooldown
- unavailable
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import time
from typing import Any, Callable, Mapping

SCHEMA = "aura.provider_health_registry.v3"
VERSION = "3.0.0"

VALID_STATES = {
    "unknown",
    "healthy",
    "degraded",
    "rate_limited",
    "cooldown",
    "unavailable",
}

TRANSIENT_FAILURES = {
    "timeout",
    "network",
    "server_error",
    "empty_response",
    "overloaded",
    "connection_error",
}
RATE_LIMIT_FAILURES = {"rate_limit", "quota", "429"}
HARD_FAILURES = {"auth", "invalid_api_key", "configuration", "forbidden"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _provider(value: Any) -> str:
    return str(value or "").strip().casefold()


@dataclass(frozen=True)
class ProviderHealthPolicyV3:
    degraded_after_failures: int = 1
    cooldown_after_failures: int = 3
    cooldown_seconds: float = 30.0
    rate_limit_cooldown_seconds: float = 60.0
    recovery_successes: int = 1
    max_error_history: int = 12


@dataclass(frozen=True)
class ProviderHealthSnapshotV3:
    schema: str
    version: str
    provider: str
    state: str
    eligible: bool
    consecutive_failures: int
    consecutive_successes: int
    total_successes: int
    total_failures: int
    last_latency_ms: float | None
    last_error_code: str
    blocked_until_monotonic: float | None
    cooldown_remaining_seconds: float
    updated_at_utc: str | None
    reason_codes: tuple[str, ...]
    error_history: tuple[Mapping[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class _ProviderState:
    __slots__ = (
        "state",
        "consecutive_failures",
        "consecutive_successes",
        "total_successes",
        "total_failures",
        "last_latency_ms",
        "last_error_code",
        "blocked_until",
        "updated_at_utc",
        "error_history",
    )

    def __init__(self) -> None:
        self.state = "unknown"
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.total_successes = 0
        self.total_failures = 0
        self.last_latency_ms: float | None = None
        self.last_error_code = ""
        self.blocked_until: float | None = None
        self.updated_at_utc: str | None = None
        self.error_history: list[dict[str, Any]] = []


class ProviderHealthRegistryV3:
    """Neutral health facts for provider routing.

    The registry intentionally contains no provider preference or quality score.
    """

    def __init__(
        self,
        policy: ProviderHealthPolicyV3 | Mapping[str, Any] | None = None,
        *,
        monotonic_clock: Callable[[], float] | None = None,
    ) -> None:
        if policy is None:
            self.policy = ProviderHealthPolicyV3()
        elif isinstance(policy, ProviderHealthPolicyV3):
            self.policy = policy
        elif isinstance(policy, Mapping):
            self.policy = ProviderHealthPolicyV3(**dict(policy))
        else:
            raise TypeError("policy must be ProviderHealthPolicyV3, mapping or None")

        self._clock = monotonic_clock or time.monotonic
        self._states: dict[str, _ProviderState] = {}

    def _state(self, provider: str) -> _ProviderState:
        key = _provider(provider)
        if not key:
            raise ValueError("provider is required")
        if key not in self._states:
            self._states[key] = _ProviderState()
        return self._states[key]

    def record_success(
        self,
        provider: str,
        *,
        latency_ms: float | None = None,
    ) -> ProviderHealthSnapshotV3:
        key = _provider(provider)
        st = self._state(key)
        st.total_successes += 1
        st.consecutive_successes += 1
        st.consecutive_failures = 0
        st.last_error_code = ""
        st.blocked_until = None
        st.updated_at_utc = _utc_now()

        if latency_ms is not None:
            st.last_latency_ms = max(0.0, float(latency_ms))

        if st.consecutive_successes >= max(1, int(self.policy.recovery_successes)):
            st.state = "healthy"
        elif st.state in {"unknown", "unavailable", "cooldown", "rate_limited"}:
            st.state = "degraded"

        return self.snapshot(key)

    def record_failure(
        self,
        provider: str,
        *,
        error_code: str,
        retry_after_seconds: float | None = None,
        latency_ms: float | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ProviderHealthSnapshotV3:
        key = _provider(provider)
        code = str(error_code or "unknown_error").strip().casefold()
        st = self._state(key)
        now = float(self._clock())

        st.total_failures += 1
        st.consecutive_failures += 1
        st.consecutive_successes = 0
        st.last_error_code = code
        st.updated_at_utc = _utc_now()

        if latency_ms is not None:
            st.last_latency_ms = max(0.0, float(latency_ms))

        safe_meta: dict[str, Any] = {}
        if isinstance(metadata, Mapping):
            for raw_key, raw_value in list(metadata.items())[:16]:
                name = str(raw_key or "")[:80]
                folded = name.casefold()
                if any(x in folded for x in ("key", "token", "password", "secret", "authorization")):
                    safe_meta[name] = "<redacted>"
                elif isinstance(raw_value, (str, int, float, bool)) or raw_value is None:
                    safe_meta[name] = raw_value if not isinstance(raw_value, str) else raw_value[:160]

        st.error_history.append({
            "error_code": code,
            "timestamp_utc": st.updated_at_utc,
            "metadata": safe_meta,
        })
        max_hist = max(1, int(self.policy.max_error_history))
        if len(st.error_history) > max_hist:
            st.error_history = st.error_history[-max_hist:]

        if code in RATE_LIMIT_FAILURES:
            delay = (
                max(0.0, float(retry_after_seconds))
                if retry_after_seconds is not None
                else max(0.0, float(self.policy.rate_limit_cooldown_seconds))
            )
            st.state = "rate_limited"
            st.blocked_until = now + delay

        elif code in HARD_FAILURES:
            st.state = "unavailable"
            st.blocked_until = None

        else:
            threshold = max(1, int(self.policy.cooldown_after_failures))
            if st.consecutive_failures >= threshold:
                st.state = "cooldown"
                st.blocked_until = now + max(0.0, float(self.policy.cooldown_seconds))
            elif st.consecutive_failures >= max(1, int(self.policy.degraded_after_failures)):
                st.state = "degraded"
                st.blocked_until = None
            else:
                st.state = "unknown"
                st.blocked_until = None

        return self.snapshot(key)

    def mark_unavailable(
        self,
        provider: str,
        *,
        reason_code: str = "manual_unavailable",
    ) -> ProviderHealthSnapshotV3:
        key = _provider(provider)
        st = self._state(key)
        st.state = "unavailable"
        st.blocked_until = None
        st.last_error_code = str(reason_code or "manual_unavailable").casefold()
        st.updated_at_utc = _utc_now()
        return self.snapshot(key)

    def reset(self, provider: str) -> ProviderHealthSnapshotV3:
        key = _provider(provider)
        self._states[key] = _ProviderState()
        return self.snapshot(key)

    def snapshot(self, provider: str) -> ProviderHealthSnapshotV3:
        key = _provider(provider)
        st = self._state(key)
        now = float(self._clock())

        state = st.state
        blocked_until = st.blocked_until
        remaining = 0.0
        reasons: list[str] = []

        if blocked_until is not None:
            remaining = max(0.0, blocked_until - now)
            if remaining <= 0.0 and state in {"cooldown", "rate_limited"}:
                # Expired blocks become degraded until a real success confirms recovery.
                state = "degraded"
                st.state = "degraded"
                st.blocked_until = None
                blocked_until = None
                reasons.append("BLOCK_EXPIRED_AWAITING_RECOVERY")

        if state == "healthy":
            eligible = True
            reasons.append("HEALTHY")
        elif state == "degraded":
            eligible = True
            reasons.append("DEGRADED_BUT_ELIGIBLE")
        elif state == "unknown":
            eligible = True
            reasons.append("UNKNOWN_ALLOWED_FOR_PROBE")
        elif state == "rate_limited":
            eligible = False
            reasons.append("RATE_LIMITED")
        elif state == "cooldown":
            eligible = False
            reasons.append("COOLDOWN_ACTIVE")
        else:
            eligible = False
            reasons.append("UNAVAILABLE")

        return ProviderHealthSnapshotV3(
            schema=SCHEMA,
            version=VERSION,
            provider=key,
            state=state,
            eligible=eligible,
            consecutive_failures=int(st.consecutive_failures),
            consecutive_successes=int(st.consecutive_successes),
            total_successes=int(st.total_successes),
            total_failures=int(st.total_failures),
            last_latency_ms=st.last_latency_ms,
            last_error_code=st.last_error_code,
            blocked_until_monotonic=blocked_until,
            cooldown_remaining_seconds=float(remaining),
            updated_at_utc=st.updated_at_utc,
            reason_codes=tuple(reasons),
            error_history=tuple(dict(x) for x in st.error_history),
        )

    def availability_map(self) -> dict[str, bool]:
        return {
            provider: self.snapshot(provider).eligible
            for provider in sorted(self._states)
        }

    def snapshots(self) -> dict[str, ProviderHealthSnapshotV3]:
        return {
            provider: self.snapshot(provider)
            for provider in sorted(self._states)
        }
