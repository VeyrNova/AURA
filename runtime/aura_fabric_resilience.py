
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import random
import time

from runtime.aura_fabric_protocols import CanonicalRequest, CanonicalResponse, new_id

RETRYABLE_HTTP = {408, 409, 425, 429, 500, 502, 503, 504}
NONRETRYABLE_HTTP = {400, 401, 403, 404, 405, 406, 410, 413, 415, 422}

@dataclass(frozen=True)
class RetryPolicy:
    max_retries_per_route: int = 3
    base_delay_s: float = 0.25
    max_delay_s: float = 8.0
    jitter_ratio: float = 0.20
    max_total_attempts: int = 12
    max_retry_after_s: float = 30.0

@dataclass(frozen=True)
class FailureClass:
    retryable: bool
    category: str
    status_code: int | None = None
    retry_after_s: float | None = None

def classify_failure(exc: Exception) -> FailureClass:
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None) if response is not None else None
    try:
        status = int(status) if status is not None else None
    except Exception:
        status = None

    retry_after = getattr(exc, "retry_after", None)
    try:
        retry_after = float(retry_after) if retry_after is not None else None
    except Exception:
        retry_after = None

    name = type(exc).__name__.lower()
    text = str(exc).lower()

    if status in RETRYABLE_HTTP:
        return FailureClass(True, "http_retryable", status, retry_after)
    if status in NONRETRYABLE_HTTP:
        return FailureClass(False, "http_nonretryable", status, retry_after)
    if any(x in name or x in text for x in ("timeout", "temporar", "connection", "overload", "rate limit", "ratelimit", "unavailable")):
        return FailureClass(True, "transport_or_capacity", status, retry_after)
    if any(x in name or x in text for x in ("auth", "permission", "invalid request", "validation", "bad request")):
        return FailureClass(False, "request_or_auth", status, retry_after)
    return FailureClass(False, "unknown_nonretryable", status, retry_after)

def _delay(policy: RetryPolicy, retry_index: int, failure: FailureClass) -> float:
    if failure.retry_after_s is not None:
        return max(0.0, min(policy.max_retry_after_s, failure.retry_after_s))
    base = min(policy.max_delay_s, policy.base_delay_s * (2 ** max(0, retry_index - 1)))
    jitter = base * policy.jitter_ratio
    return max(0.0, min(policy.max_delay_s, base + random.uniform(-jitter, jitter)))

def execute_with_resilience(service: Any, request: CanonicalRequest) -> CanonicalResponse:
    policy = RetryPolicy(
        max_retries_per_route=max(1, int(getattr(service, "retries_per_model", 3))),
    )
    with service._lock:
        service.requests_total += 1

    decision = service.registry.route(service._route_request(request))
    candidates = (decision.primary,) + decision.fallbacks
    attempts: list[dict[str, Any]] = []
    chosen: tuple[str, str] | None = None
    result = None
    total_attempts = 0
    failover_count = 0
    last_error = None

    for candidate_index, candidate in enumerate(candidates):
        if total_attempts >= policy.max_total_attempts:
            break
        slug = candidate.slug
        provider_id = slug.split("/", 1)[0]
        adapter = service.adapters.get(provider_id)
        if adapter is None:
            attempts.append({"route": slug, "attempt": 0, "ok": False, "classification": "adapter_missing"})
            continue

        for attempt in range(1, policy.max_retries_per_route + 1):
            if total_attempts >= policy.max_total_attempts:
                break
            total_attempts += 1
            started = time.monotonic()
            try:
                result = adapter.generate(request, slug)
                latency_ms = (time.monotonic() - started) * 1000.0
                service.registry.record_result(slug, success=True, latency_ms=latency_ms)
                attempts.append({
                    "route": slug, "attempt": attempt, "ok": True,
                    "latency_ms": round(latency_ms, 3),
                })
                chosen = (provider_id, slug)
                break
            except Exception as exc:
                last_error = exc
                latency_ms = (time.monotonic() - started) * 1000.0
                failure = classify_failure(exc)
                service.registry.record_result(slug, success=False, latency_ms=latency_ms)
                record = {
                    "route": slug, "attempt": attempt, "ok": False,
                    "latency_ms": round(latency_ms, 3),
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:300],
                    "classification": failure.category,
                    "retryable": failure.retryable,
                    "status_code": failure.status_code,
                }
                attempts.append(record)

                if not failure.retryable or attempt >= policy.max_retries_per_route:
                    break

                delay_s = _delay(policy, attempt, failure)
                record["scheduled_backoff_s"] = round(delay_s, 3)
                if os_test_no_sleep():
                    record["sleep_skipped_for_test"] = True
                else:
                    time.sleep(delay_s)

        if chosen is not None:
            if candidate_index > 0:
                failover_count += 1
                with service._lock:
                    service.failovers_total += 1
            break

    if chosen is None or result is None:
        with service._lock:
            service.requests_failed += 1
        summary = " | ".join(
            f"{a.get('route')}#{a.get('attempt')}:{a.get('classification')}:{a.get('error','')}"
            for a in attempts[-8:]
        )
        raise RuntimeError("AURA Fabric Gateway exhausted all routes: " + summary) from last_error

    response = CanonicalResponse(
        response_id=new_id("resp"),
        request_id=request.request_id,
        requested_model=request.model,
        routed_model=chosen[1],
        provider_id=chosen[0],
        text=result.text,
        finish_reason=result.finish_reason,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        tool_calls=tuple(result.tool_calls),
        metadata={
            "attempts": attempts,
            "failover_used": candidate_index > 0,
            "failover_count": failover_count,
            "resilience_policy": {
                "max_retries_per_route": policy.max_retries_per_route,
                "max_total_attempts": policy.max_total_attempts,
                "retryable_http": sorted(RETRYABLE_HTTP),
            },
            **dict(result.metadata),
        },
    )
    with service._lock:
        service.last_route = {
            "request_id": request.request_id,
            "requested_model": request.model,
            "routed_model": chosen[1],
            "provider_id": chosen[0],
            "attempts": attempts,
        }
    return response

def os_test_no_sleep() -> bool:
    import os
    return os.environ.get("AURA_FABRIC_TEST_NO_SLEEP", "0") == "1"
