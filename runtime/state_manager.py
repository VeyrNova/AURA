"""Canonical runtime-state vocabulary for AURA Runtime v2 foundation.

This module is intentionally independent from Qt.  The existing Qt EventBus
continues to transport state changes; later UI work can subscribe to the same
stable vocabulary without importing the Core implementation.
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from time import monotonic

CANONICAL_STATES = {
    "IDLE",
    "LISTENING",
    "TRANSCRIBING",
    "THINKING",
    "SEARCHING",
    "ANALYZING",
    "ACTING",
    "WAITING_CONFIRMATION",
    "SPEAKING",
    "PAUSED",
    "OFFLINE",
    "ERROR",
}

# Historical state names accepted during the migration to Runtime v2.
_STATE_ALIASES = {
    "PROCESSING": "ANALYZING",
    "EXECUTING": "ACTING",
}


def normalize_state(state: str) -> str:
    value = str(state or "IDLE").strip().upper()
    value = _STATE_ALIASES.get(value, value)
    return value if value in CANONICAL_STATES else "ERROR"


@dataclass(frozen=True)
class RuntimeStateSnapshot:
    state: str = "IDLE"
    previous: str = "IDLE"
    reason: str = "startup"
    changed_at: float = 0.0
    revision: int = 0


class RuntimeStateManager:
    """Thread-safe single source of truth for AURA's visible activity state."""

    def __init__(self) -> None:
        self._lock = RLock()
        now = monotonic()
        self._snapshot = RuntimeStateSnapshot(changed_at=now)

    def set(self, state: str, *, reason: str = "") -> RuntimeStateSnapshot:
        normalized = normalize_state(state)
        with self._lock:
            current = self._snapshot
            if normalized == current.state and not reason:
                return current
            self._snapshot = RuntimeStateSnapshot(
                state=normalized,
                previous=current.state,
                reason=str(reason or current.reason or "runtime"),
                changed_at=monotonic(),
                revision=current.revision + 1,
            )
            return self._snapshot

    def snapshot(self) -> RuntimeStateSnapshot:
        with self._lock:
            return self._snapshot


runtime_state = RuntimeStateManager()
