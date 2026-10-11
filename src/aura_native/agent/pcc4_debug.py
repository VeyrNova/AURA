"""Safe opt-in diagnostics for PCC-4 provider routing.

Only identifiers needed to prove routing are accepted. Conversation content,
credentials, HTTP data and provider URLs have no place in this boundary.
"""
from __future__ import annotations

import os
import re
import sys


_EVENTS = frozenset({
    "PCC4_REQUEST_CREATED",
    "PCC4_PROVIDER_RESOLVED",
    "PCC4_STREAM_STARTED",
    "PCC4_FIRST_DELTA",
    "PCC4_COMPLETED",
    "PCC4_CANCEL_REQUESTED",
    "PCC4_CANCELLED",
    "PCC4_ERROR",
    "PCC4_RETRY_SCHEDULED",
    "PCC4_RETRY_STARTED",
})
_SAFE_VALUE = re.compile(r"[^A-Za-z0-9._:/-]+")


def _safe(value: object, *, limit: int = 160) -> str:
    return _SAFE_VALUE.sub("_", str(value or ""))[:limit]


def pcc4_trace(
    event: str,
    *,
    provider: object = "",
    model: object = "",
    request_id: object = "",
    error_code: object = "",
    http_status: object = "",
    stage: object = "",
    attempt: object = "",
    next_attempt: object = "",
    delay_ms: object = "",
    environment=None,
    stream=None,
) -> None:
    """Emit one content-free diagnostic line when explicitly enabled."""
    env = os.environ if environment is None else environment
    if env.get("AURA_PCC4_DEBUG") != "1" or event not in _EVENTS:
        return
    fields = (
        ("provider", provider),
        ("model", model),
        ("request_id", request_id),
        ("error", error_code),
        ("http_status", http_status),
        ("stage", stage),
        ("attempt", attempt),
        ("next_attempt", next_attempt),
        ("delay_ms", delay_ms),
    )
    suffix = " ".join(f"{name}={_safe(value)}" for name, value in fields if value)
    print(event + (" " + suffix if suffix else ""), file=stream or sys.stderr, flush=True)
