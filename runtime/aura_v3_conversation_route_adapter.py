from __future__ import annotations

"""AURA v3 conversation route adapter.

Compatibility bridge for the existing LLMWorker ``fabric_auto`` lane.

This module intentionally does NOT import MainWindow, does NOT own a new Fabric
GatewayService, and does NOT call provider HTTP APIs. At execution time it
reuses the canonical conversation Fabric service/catalog, translates its exact
route entries into RouteCandidateV3 facts, calls the already-bound
AuraCore.intelligence_gateway_v3 exactly once, and returns the legacy
``fabric_result`` mapping expected by the current UI telemetry/metrics path.
"""

from dataclasses import asdict
from typing import Any, Iterable, Mapping

from runtime.aura_conversation_fabric_bridge import build_canonical_request
from runtime.aura_eligibility_filter_v3 import RouteCandidateV3
from runtime.aura_intelligence_gateway_v3 import IntelligenceGatewayRequestV3
from runtime.aura_model_policy_engine_v3 import ModelPolicyRequest
from runtime.aura_model_switch_gate_v3 import (
    ModelSwitchSessionStateV3,
    RouteIdentityV3,
)

SCHEMA = "aura.v3.conversation_route_adapter"
VERSION = "3.0.0"

_VALID_MODES = {
    "automatic",
    "performance",
    "economy",
    "local_only",
    "cloud_preferred",
}
_VALID_PRIVACY = {"default", "cloud_allowed", "local_required"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _fold(value: Any) -> str:
    return _text(value).casefold()


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in {"1", "true", "yes", "on", "enabled"}:
            return True
        if lowered in {"0", "false", "no", "off", "disabled"}:
            return False
    return bool(value)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _last_user_text(messages: Iterable[Mapping[str, Any]]) -> str:
    items = list(messages or ())
    for item in reversed(items):
        if not isinstance(item, Mapping):
            continue
        if _fold(item.get("role")) == "user":
            return str(item.get("content") or "")
    return ""


def _canonical_fabric_service() -> Any:
    # Local import preserves lazy singleton ownership in the existing bridge.
    from runtime import aura_conversation_fabric_bridge as bridge

    provider = getattr(bridge, "_get_service", None)
    if not callable(provider):
        raise RuntimeError("canonical conversation Fabric _get_service is unavailable")
    service = provider()
    if service is None:
        raise RuntimeError("canonical conversation Fabric service is unavailable")
    return service


def _policy_provider(entry: Any) -> str:
    provider_id = _fold(getattr(entry, "provider_id", ""))
    is_local = bool(getattr(entry, "local", False)) or provider_id in {
        "ollama",
        "local",
    }
    return "local" if is_local else provider_id


def _route_identities(entry: Any) -> tuple[str, ...]:
    """Return policy-visible model identities for one exact Fabric route.

    The legacy ResourceGuardian may expose either the Fabric public model id or
    the provider-native model name. We publish both identities when they differ,
    while keeping the exact Fabric route slug only in metadata.
    """
    values: list[str] = []

    public_id = _text(getattr(entry, "public_id", ""))
    if public_id:
        values.append(public_id)

    raw_model = _text(getattr(entry, "model", ""))
    if raw_model:
        values.append(raw_model)

    slug = _text(getattr(entry, "slug", ""))
    if "/" in slug:
        tail = slug.split("/", 1)[1].strip()
        if tail:
            values.append(tail)

    out: list[str] = []
    seen = set()
    for value in values:
        key = value.casefold()
        if not value or key in seen:
            continue
        seen.add(key)
        out.append(value)
    return tuple(out)


def _context_window(entry: Any) -> int | None:
    capabilities = getattr(entry, "capabilities", None)
    for owner in (capabilities, entry):
        if owner is None:
            continue
        for name in ("max_context_tokens", "context_window", "num_ctx"):
            value = getattr(owner, name, None)
            parsed = _int_or_none(value)
            if parsed is not None and parsed > 0:
                return parsed
    return None


def _fabric_candidates(service: Any) -> tuple[RouteCandidateV3, ...]:
    catalog = getattr(service, "catalog", None)
    entries = getattr(catalog, "entries", None)
    if not callable(entries):
        raise RuntimeError("Fabric service catalog.entries() is unavailable")

    candidates: list[RouteCandidateV3] = []
    seen: set[tuple[str, str, str]] = set()

    for entry in tuple(entries()):
        route_slug = _text(getattr(entry, "slug", ""))
        provider_id = _fold(getattr(entry, "provider_id", ""))
        provider = _policy_provider(entry)
        if not route_slug or not provider:
            continue

        identities = _route_identities(entry)
        if not identities:
            # Fail closed for entries that cannot be reconciled with
            # ModelPolicyEngineV3's provider/model identity contract.
            continue

        is_local = provider == "local"
        enabled = bool(getattr(entry, "enabled", True))
        public_id = _text(getattr(entry, "public_id", ""))

        for model_identity in identities:
            key = (provider, model_identity.casefold(), route_slug.casefold())
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                RouteCandidateV3(
                    provider=provider,
                    model=model_identity,
                    enabled=enabled,
                    requires_network=not is_local,
                    uses_local_gpu=is_local,
                    context_window=_context_window(entry),
                    supported_tasks=("chat",),
                    metadata={
                        "fabric_route_slug": route_slug,
                        "fabric_provider_id": provider_id,
                        "fabric_public_id": public_id,
                        "fabric_local": is_local,
                    },
                )
            )

    if not candidates:
        raise RuntimeError("Fabric catalog exposed no usable v3 conversation routes")
    return tuple(candidates)


def _mode(profile: Mapping[str, Any]) -> str:
    raw = _fold(
        profile.get("_aura_v3_mode")
        or profile.get("intelligence_mode")
        or "automatic"
    )
    return raw if raw in _VALID_MODES else "automatic"


def _privacy(profile: Mapping[str, Any]) -> str:
    raw = _fold(
        profile.get("_aura_v3_privacy")
        or profile.get("privacy")
        or "default"
    )
    return raw if raw in _VALID_PRIVACY else "default"


def _preferred_provider(profile: Mapping[str, Any]) -> str | None:
    # Deliberately do not reinterpret the legacy ``profile['provider']`` route
    # as an explicit user preference. It is a ResourceGuardian outcome.
    value = _fold(
        profile.get("_aura_v3_preferred_provider")
        or profile.get("preferred_provider")
    )
    if value == "ollama":
        value = "local"
    return value or None


def _xtts_hot(aura_core: Any) -> bool:
    engine = getattr(aura_core, "voice_engine", None)
    fn = getattr(engine, "xtts_model_loaded", None)
    if not callable(fn):
        return False
    try:
        return bool(fn())
    except Exception:
        return False


def _session_state(aura_core: Any) -> ModelSwitchSessionStateV3:
    value = getattr(aura_core, "_aura_v3_model_switch_session_state", None)
    if isinstance(value, ModelSwitchSessionStateV3):
        return value
    if isinstance(value, Mapping):
        current_raw = value.get("current")
        current = None
        if isinstance(current_raw, Mapping):
            current = RouteIdentityV3(
                provider=_text(current_raw.get("provider")),
                model=_text(current_raw.get("model")),
            )
        return ModelSwitchSessionStateV3(
            current=current,
            turns_on_current=max(0, int(value.get("turns_on_current") or 0)),
            turns_since_switch=max(0, int(value.get("turns_since_switch") or 0)),
            current_warm=bool(value.get("current_warm", False)),
        )
    return ModelSwitchSessionStateV3()


def _selected_policy_identity(trace: Mapping[str, Any]) -> RouteIdentityV3 | None:
    events = trace.get("events", ()) if isinstance(trace, Mapping) else ()
    if not isinstance(events, (list, tuple)):
        return None
    for event in reversed(events):
        if not isinstance(event, Mapping):
            continue
        if _fold(event.get("stage")) != "model_switch_gate":
            continue
        provider = _text(event.get("selected_provider"))
        model = _text(event.get("selected_model"))
        if provider:
            return RouteIdentityV3(provider=provider, model=model)
    return None


def _commit_session_state(
    aura_core: Any,
    previous: ModelSwitchSessionStateV3,
    selected: RouteIdentityV3 | None,
) -> None:
    if selected is None:
        return

    old = previous.current
    if old is not None and old.key == selected.key:
        state = ModelSwitchSessionStateV3(
            current=selected,
            turns_on_current=max(1, previous.turns_on_current + 1),
            turns_since_switch=max(0, previous.turns_since_switch + 1),
            current_warm=previous.current_warm,
        )
    else:
        state = ModelSwitchSessionStateV3(
            current=selected,
            turns_on_current=1,
            turns_since_switch=0,
            current_warm=False,
        )
    setattr(aura_core, "_aura_v3_model_switch_session_state", state)


def _legacy_result(gateway_result: Any) -> dict[str, Any]:
    execution = dict(getattr(gateway_result, "execution", {}) or {})
    metadata = dict(execution.get("metadata") or {})

    attempts = list(execution.get("attempts") or ())
    failover_count = max(
        0,
        int(
            execution.get("failover_count")
            or getattr(gateway_result, "fallback_count", 0)
            or 0
        ),
    )
    latency_ms = _float(execution.get("latency_ms"), 0.0)

    provider_id = _text(
        execution.get("provider_id")
        or execution.get("provider")
        or getattr(gateway_result, "provider", "")
    )
    routed_model = _text(
        execution.get("routed_model")
        or execution.get("model")
        or getattr(gateway_result, "model", "")
    )
    requested_model = _text(
        execution.get("requested_model")
        or routed_model
    )

    return {
        "text": str(getattr(gateway_result, "text", "") or ""),
        "provider_id": provider_id,
        "routed_model": routed_model,
        "requested_model": requested_model,
        "finish_reason": _text(
            execution.get("finish_reason")
            or getattr(gateway_result, "finish_reason", "")
        ),
        "input_tokens": int(execution.get("input_tokens", 0) or 0),
        "output_tokens": int(execution.get("output_tokens", 0) or 0),
        "attempts": attempts,
        "failover_used": bool(
            execution.get("failover_used")
            or failover_count > 0
        ),
        "failover_count": failover_count,
        "latency_seconds": latency_ms / 1000.0,
        "metadata": metadata,
        "last_route": {
            "requested_model": requested_model,
            "routed_model": routed_model,
            "provider_id": provider_id,
            "attempts": attempts,
        },
        "_aura_v3_trace": dict(getattr(gateway_result, "trace", {}) or {}),
        "_aura_v3_adapter": {
            "schema": SCHEMA,
            "version": VERSION,
        },
    }


def generate_conversation_v3(
    aura_core: Any,
    generation_messages: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    profile: Mapping[str, Any] | None = None,
    voice_response: bool = False,
) -> dict[str, Any]:
    """Execute one existing ``fabric_auto`` turn through IntelligenceGatewayV3."""
    if aura_core is None:
        raise ValueError("aura_core is required")

    gateway = getattr(aura_core, "intelligence_gateway_v3", None)
    execute = getattr(gateway, "execute", None)
    if not callable(execute):
        raise RuntimeError("AuraCore.intelligence_gateway_v3 is unavailable")

    legacy_profile = dict(profile or {})
    user_text = _last_user_text(generation_messages)

    service = _canonical_fabric_service()
    candidates = _fabric_candidates(service)

    canonical_request = build_canonical_request(
        generation_messages,
        profile={
            **legacy_profile,
            "voice_response": bool(voice_response),
        },
        model="aura-default",
    )

    previous_session = _session_state(aura_core)

    policy_request = ModelPolicyRequest(
        user_text=user_text,
        task_type="chat",
        mode=_mode(legacy_profile),
        privacy=_privacy(legacy_profile),
        voice_output=bool(voice_response),
        # Existing fabric_auto returns a completed string and is consumed as a
        # one-item stream. Do not invent a true provider streaming requirement.
        streaming=False,
        preferred_provider=_preferred_provider(legacy_profile),
        latency_target_ms=_int_or_none(
            legacy_profile.get("_aura_v3_latency_target_ms")
        ),
        quality=_text(
            legacy_profile.get("_aura_v3_quality") or "balanced"
        ).casefold(),
        metadata={
            "lane": "llmworker.fabric_auto",
            "legacy_profile_name": _text(legacy_profile.get("name")),
        },
    )

    request = IntelligenceGatewayRequestV3(
        execution_payload=canonical_request,
        candidates=candidates,
        policy_request=policy_request,
        session_state=previous_session,
        correlation_id=_text(getattr(canonical_request, "request_id", "")),
        network_allowed=_bool(
            legacy_profile.get("_aura_v3_network_allowed"),
            True,
        ),
        required_context_tokens=max(
            0,
            int(legacy_profile.get("_aura_v3_required_context_tokens") or 0),
        ),
        preserve_xtts=bool(voice_response),
        xtts_hot=_xtts_hot(aura_core),
        xtts_vram_reserve_mb=max(
            0.0,
            _float(
                legacy_profile.get("_aura_v3_xtts_vram_reserve_mb"),
                0.0,
            ),
        ),
        ram_reserve_gb=max(
            0.0,
            _float(
                legacy_profile.get("_aura_v3_ram_reserve_gb"),
                0.0,
            ),
        ),
        switch_advantage_score=_float(
            legacy_profile.get("_aura_v3_switch_advantage_score"),
            0.0,
        ),
        switch_penalty=max(
            0.0,
            _float(
                legacy_profile.get("_aura_v3_switch_penalty"),
                0.0,
            ),
        ),
        proposed_warm=_bool(
            legacy_profile.get("_aura_v3_proposed_warm"),
            False,
        ),
        warm_bonus=max(
            0.0,
            _float(
                legacy_profile.get("_aura_v3_warm_bonus"),
                0.0,
            ),
        ),
        metadata={
            "lane": "llmworker.fabric_auto",
            "voice_response": bool(voice_response),
        },
    )

    result = execute(request)

    if bool(getattr(result, "blocked", False)) or not bool(
        getattr(result, "ok", False)
    ):
        code = _text(getattr(result, "error_code", "")) or "gateway_failed"
        reason = _text(getattr(result, "finish_reason", "")) or "failed"
        raise RuntimeError(f"AURA v3 conversation route failed: {code}:{reason}")

    selected = _selected_policy_identity(
        dict(getattr(result, "trace", {}) or {})
    )
    _commit_session_state(aura_core, previous_session, selected)

    return _legacy_result(result)
