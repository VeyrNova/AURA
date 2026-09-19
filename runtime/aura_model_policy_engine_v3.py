from __future__ import annotations

"""AURA Model Policy Engine v3.

Pure policy/orchestration layer. It does not probe hardware, load/unload models,
call providers, or mutate runtime state. It consumes HardwareCapabilityServiceV3
and reuses ResourceGuardian's existing route profile as the authoritative
compatibility candidate.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

SCHEMA = "aura.model_policy_engine.v3"
VERSION = "3.0.0"

VALID_MODES = {
    "automatic",
    "performance",
    "economy",
    "local_only",
    "cloud_preferred",
}
VALID_PRIVACY = {"default", "cloud_allowed", "local_required"}


@dataclass(frozen=True)
class ModelPolicyRequest:
    user_text: str = ""
    task_type: str = "chat"
    mode: str = "automatic"
    privacy: str = "default"
    voice_output: bool = False
    streaming: bool = True
    preferred_provider: str | None = None
    latency_target_ms: int | None = None
    quality: str = "balanced"
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelPolicyDecision:
    schema: str
    version: str
    created_at_utc: str
    mode: str
    task_type: str
    privacy: str
    primary: Mapping[str, Any]
    fallback_chain: tuple[Mapping[str, Any], ...]
    constraints: Mapping[str, Any]
    reason_codes: tuple[str, ...]
    capability_summary: Mapping[str, Any]
    blocked: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _provider_name(value: Any) -> str:
    return str(value or "").strip().casefold()


def _route_data(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        if value.get("available") is False:
            return {}
        data = value.get("data", value)
        return dict(data) if isinstance(data, Mapping) else {}
    return {}


def _provider_state(value: Any) -> dict[str, bool]:
    data = _route_data(value)
    return {
        "groq": bool(data.get("groq", False)),
        "gemini": bool(data.get("gemini", False)),
        "any_remote": bool(data.get("any_remote", False)),
    }


def _models(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, Mapping) or value.get("available") is False:
        return ()
    raw = value.get("data", ())
    if not isinstance(raw, (list, tuple)):
        return ()
    return tuple(dict(item) for item in raw if isinstance(item, Mapping))


class ModelPolicyEngineV3:
    """Decision layer for the future Intelligence Gateway.

    Existing ResourceGuardian routing remains authoritative for compatibility.
    Product modes constrain or reorder viable routes without duplicating model
    fit calculations or hardware detection.
    """

    def __init__(self, capability_service: Any) -> None:
        if capability_service is None:
            raise ValueError("capability_service is required")
        self.capabilities = capability_service

    @staticmethod
    def _normalize_request(request: ModelPolicyRequest | Mapping[str, Any]) -> ModelPolicyRequest:
        if isinstance(request, ModelPolicyRequest):
            raw = request
        elif isinstance(request, Mapping):
            raw = ModelPolicyRequest(**dict(request))
        else:
            raise TypeError("request must be ModelPolicyRequest or mapping")

        mode = str(raw.mode or "automatic").strip().casefold()
        privacy = str(raw.privacy or "default").strip().casefold()
        if mode not in VALID_MODES:
            mode = "automatic"
        if privacy not in VALID_PRIVACY:
            privacy = "default"

        return ModelPolicyRequest(
            user_text=str(raw.user_text or ""),
            task_type=str(raw.task_type or "chat").strip().casefold() or "chat",
            mode=mode,
            privacy=privacy,
            voice_output=bool(raw.voice_output),
            streaming=bool(raw.streaming),
            preferred_provider=(
                str(raw.preferred_provider).strip().casefold()
                if raw.preferred_provider
                else None
            ),
            latency_target_ms=(
                max(1, int(raw.latency_target_ms))
                if raw.latency_target_ms is not None
                else None
            ),
            quality=str(raw.quality or "balanced").strip().casefold() or "balanced",
            metadata=dict(raw.metadata or {}),
        )

    @staticmethod
    def _route(provider: str, model: str | None = None, *, source: str, reason: str) -> dict[str, Any]:
        return {
            "provider": _provider_name(provider),
            "model": str(model or ""),
            "source": str(source),
            "reason": str(reason),
        }

    @staticmethod
    def _dedupe_routes(routes: list[Mapping[str, Any]]) -> tuple[Mapping[str, Any], ...]:
        seen = set()
        out = []
        for raw in routes:
            provider = _provider_name(raw.get("provider"))
            model = str(raw.get("model") or "")
            if not provider:
                continue
            key = (provider, model)
            if key in seen:
                continue
            seen.add(key)
            out.append(dict(raw))
        return tuple(out)

    def decide(self, request: ModelPolicyRequest | Mapping[str, Any]) -> ModelPolicyDecision:
        req = self._normalize_request(request)
        force_local = req.mode == "local_only" or req.privacy == "local_required"

        route_result = self.capabilities.route_profile(
            voice_output=req.voice_output,
            user_text=req.user_text,
            force_local=force_local,
            preferred_provider=req.preferred_provider,
        )
        provider_result = self.capabilities.provider_availability()
        model_result = self.capabilities.local_model_catalog(force=False)
        resource_result = self.capabilities.resource_snapshot(
            include_ollama=False,
            force_gpu=False,
        )
        gpu_result = self.capabilities.gpu_runtime_snapshot()

        existing = _route_data(route_result)
        remote = _provider_state(provider_result)
        installed = _models(model_result)

        existing_provider = _provider_name(existing.get("provider"))
        existing_model = str(existing.get("model") or "")
        local_available = bool(installed) or existing_provider == "local"

        reasons: list[str] = []
        candidates: list[Mapping[str, Any]] = []

        # Explicit local/privacy mode is a hard constraint.
        if force_local:
            reasons.append("LOCAL_REQUIRED")
            if existing_provider == "local":
                primary = self._route(
                    "local",
                    existing_model,
                    source="ResourceGuardian.llm_request_profile",
                    reason="forced-local existing compatible route",
                )
            elif local_available:
                primary = self._route(
                    "local",
                    existing_model,
                    source="HardwareCapabilityServiceV3.local_model_catalog",
                    reason="local route required; exact model remains owned by existing model policy",
                )
            else:
                primary = self._route(
                    "blocked",
                    "",
                    source="ModelPolicyEngineV3",
                    reason="local route required but no local model is available",
                )
                return ModelPolicyDecision(
                    schema=SCHEMA,
                    version=VERSION,
                    created_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    mode=req.mode,
                    task_type=req.task_type,
                    privacy=req.privacy,
                    primary=primary,
                    fallback_chain=(),
                    constraints={
                        "cloud_allowed": False,
                        "local_required": True,
                        "streaming": req.streaming,
                        "voice_output": req.voice_output,
                        "latency_target_ms": req.latency_target_ms,
                        "quality": req.quality,
                    },
                    reason_codes=tuple(reasons + ["NO_LOCAL_MODEL_AVAILABLE"]),
                    capability_summary={
                        "local_model_count": len(installed),
                        "remote": remote,
                        "resource": _route_data(resource_result),
                        "gpu_runtime": _route_data(gpu_result),
                    },
                    blocked=True,
                )

            return ModelPolicyDecision(
                schema=SCHEMA,
                version=VERSION,
                created_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                mode=req.mode,
                task_type=req.task_type,
                privacy=req.privacy,
                primary=primary,
                fallback_chain=(),
                constraints={
                    "cloud_allowed": False,
                    "local_required": True,
                    "streaming": req.streaming,
                    "voice_output": req.voice_output,
                    "latency_target_ms": req.latency_target_ms,
                    "quality": req.quality,
                },
                reason_codes=tuple(reasons),
                capability_summary={
                    "local_model_count": len(installed),
                    "remote": remote,
                    "resource": _route_data(resource_result),
                    "gpu_runtime": _route_data(gpu_result),
                },
                blocked=False,
            )

        # Explicit provider is honored when it is currently available.
        preferred = _provider_name(req.preferred_provider)
        if preferred in {"groq", "gemini"} and remote.get(preferred, False):
            primary = self._route(
                preferred,
                existing_model if existing_provider == preferred else "",
                source="explicit-preference",
                reason="preferred remote provider is available",
            )
            reasons.append("EXPLICIT_PROVIDER_AVAILABLE")
        elif preferred == "local" and local_available:
            primary = self._route(
                "local",
                existing_model if existing_provider == "local" else "",
                source="explicit-preference",
                reason="preferred local provider is available",
            )
            reasons.append("EXPLICIT_LOCAL_AVAILABLE")
        elif req.mode == "cloud_preferred" and remote["any_remote"]:
            chosen = "groq" if remote["groq"] else "gemini"
            primary = self._route(
                chosen,
                existing_model if existing_provider == chosen else "",
                source="cloud-preferred",
                reason="cloud preferred and a configured remote provider is available",
            )
            reasons.append("CLOUD_PREFERRED")
        elif existing_provider and existing_provider != "blocked":
            primary = self._route(
                existing_provider,
                existing_model,
                source="ResourceGuardian.llm_request_profile",
                reason="existing AURA route preserved",
            )
            reasons.append("EXISTING_ROUTE_PRESERVED")
        elif remote["any_remote"]:
            chosen = "groq" if remote["groq"] else "gemini"
            primary = self._route(
                chosen,
                "",
                source="provider-availability",
                reason="existing route unavailable; remote provider available",
            )
            reasons.append("REMOTE_RECOVERY_ROUTE")
        elif local_available:
            primary = self._route(
                "local",
                existing_model,
                source="local-model-catalog",
                reason="existing route unavailable; local model available",
            )
            reasons.append("LOCAL_RECOVERY_ROUTE")
        else:
            primary = self._route(
                "blocked",
                "",
                source="ModelPolicyEngineV3",
                reason="no viable local or remote route",
            )
            reasons.append("NO_VIABLE_ROUTE")

        # Fallback ordering stays neutral: preserve existing candidate first, then
        # other currently available routes. No provider quality ranking is invented.
        if existing_provider and existing_provider != primary["provider"]:
            candidates.append(self._route(
                existing_provider,
                existing_model,
                source="ResourceGuardian.llm_request_profile",
                reason="existing compatibility fallback",
            ))
        if local_available and primary["provider"] != "local":
            candidates.append(self._route(
                "local",
                existing_model if existing_provider == "local" else "",
                source="local-model-catalog",
                reason="local fallback available",
            ))
        for provider in ("groq", "gemini"):
            if remote.get(provider, False) and primary["provider"] != provider:
                candidates.append(self._route(
                    provider,
                    existing_model if existing_provider == provider else "",
                    source="provider-availability",
                    reason="configured remote fallback available",
                ))

        blocked = primary["provider"] == "blocked"
        return ModelPolicyDecision(
            schema=SCHEMA,
            version=VERSION,
            created_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            mode=req.mode,
            task_type=req.task_type,
            privacy=req.privacy,
            primary=primary,
            fallback_chain=self._dedupe_routes(candidates),
            constraints={
                "cloud_allowed": req.privacy != "local_required",
                "local_required": False,
                "streaming": req.streaming,
                "voice_output": req.voice_output,
                "latency_target_ms": req.latency_target_ms,
                "quality": req.quality,
                "performance_hint": req.mode == "performance",
                "economy_hint": req.mode == "economy",
            },
            reason_codes=tuple(reasons),
            capability_summary={
                "local_model_count": len(installed),
                "remote": remote,
                "resource": _route_data(resource_result),
                "gpu_runtime": _route_data(gpu_result),
            },
            blocked=blocked,
        )
