from __future__ import annotations

"""AURA Eligibility Filter v3.

Hard-constraint filter inspired by the fail-closed selection pattern observed in
vLLM Semantic Router. This layer does not score or rank routes. It only removes
candidates that are not allowed or cannot safely satisfy the request.

No hardware probing, provider calls, model loading, or runtime mutation occurs
here. All capability/resource facts must be supplied by AURA's existing
HardwareCapabilityServiceV3 / ResourceGuardian / future health registry.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping

SCHEMA = "aura.eligibility_filter.v3"
VERSION = "3.0.0"


@dataclass(frozen=True)
class EligibilityRequestV3:
    task_type: str = "chat"
    mode: str = "automatic"
    privacy: str = "default"
    required_context_tokens: int = 0
    network_allowed: bool = True
    preserve_xtts: bool = True
    xtts_hot: bool = False
    xtts_vram_reserve_mb: float = 0.0
    ram_reserve_gb: float = 0.0


@dataclass(frozen=True)
class RouteCandidateV3:
    provider: str
    model: str = ""
    enabled: bool = True
    requires_network: bool = False
    uses_local_gpu: bool = False
    context_window: int | None = None
    min_ram_gb: float | None = None
    min_vram_mb: float | None = None
    supported_tasks: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EligibilityRejectionV3:
    provider: str
    model: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class EligibilityResultV3:
    schema: str
    version: str
    eligible: tuple[RouteCandidateV3, ...]
    rejected: tuple[EligibilityRejectionV3, ...]
    fail_closed: bool
    error_code: str | None
    facts: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _name(value: Any) -> str:
    return str(value or "").strip().casefold()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _resource_data(resource_snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(resource_snapshot, Mapping):
        return {}
    if resource_snapshot.get("available") is False:
        return {}
    data = resource_snapshot.get("data", resource_snapshot)
    return dict(data) if isinstance(data, Mapping) else {}


def _provider_data(provider_availability: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(provider_availability, Mapping):
        return {}
    if provider_availability.get("available") is False:
        return {}
    data = provider_availability.get("data", provider_availability)
    return dict(data) if isinstance(data, Mapping) else {}


class EligibilityFilterV3:
    """Apply hard eligibility constraints while preserving candidate order."""

    def filter(
        self,
        candidates: Iterable[RouteCandidateV3 | Mapping[str, Any]],
        request: EligibilityRequestV3 | Mapping[str, Any],
        *,
        resource_snapshot: Mapping[str, Any] | None = None,
        provider_availability: Mapping[str, Any] | None = None,
        installed_local_models: Iterable[str] | None = None,
    ) -> EligibilityResultV3:
        if isinstance(request, EligibilityRequestV3):
            req = request
        elif isinstance(request, Mapping):
            req = EligibilityRequestV3(**dict(request))
        else:
            raise TypeError("request must be EligibilityRequestV3 or mapping")

        normalized: list[RouteCandidateV3] = []
        for raw in candidates:
            if isinstance(raw, RouteCandidateV3):
                normalized.append(raw)
            elif isinstance(raw, Mapping):
                item = dict(raw)
                if "supported_tasks" in item and isinstance(item["supported_tasks"], list):
                    item["supported_tasks"] = tuple(item["supported_tasks"])
                normalized.append(RouteCandidateV3(**item))
            else:
                raise TypeError("candidate must be RouteCandidateV3 or mapping")

        resource = _resource_data(resource_snapshot)
        providers = _provider_data(provider_availability)

        installed_known = installed_local_models is not None
        installed = {
            str(x or "").strip().casefold()
            for x in (installed_local_models or ())
            if str(x or "").strip()
        }

        ram_available_gb = _float(
            resource.get("ram_available_gb", resource.get("ram_free_gb", 0.0))
        )
        vram_total_mb = _float(resource.get("vram_total_mb", 0.0))
        vram_used_mb = _float(resource.get("vram_used_mb", 0.0))
        raw_vram_free_mb = max(0.0, vram_total_mb - vram_used_mb)

        xtts_reserve = (
            max(0.0, _float(req.xtts_vram_reserve_mb))
            if req.preserve_xtts and req.xtts_hot
            else 0.0
        )
        safe_vram_free_mb = max(0.0, raw_vram_free_mb - xtts_reserve)
        safe_ram_available_gb = max(0.0, ram_available_gb - max(0.0, _float(req.ram_reserve_gb)))

        local_required = (
            _name(req.mode) == "local_only"
            or _name(req.privacy) == "local_required"
        )

        eligible: list[RouteCandidateV3] = []
        rejected: list[EligibilityRejectionV3] = []

        for candidate in normalized:
            provider = _name(candidate.provider)
            model = str(candidate.model or "").strip()
            reasons: list[str] = []

            if not candidate.enabled:
                reasons.append("CANDIDATE_DISABLED")

            if not provider:
                reasons.append("PROVIDER_MISSING")

            if local_required and provider != "local":
                reasons.append("LOCAL_REQUIRED")

            if candidate.requires_network and not bool(req.network_allowed):
                reasons.append("NETWORK_FORBIDDEN")

            # Availability is a hard rejection only when AURA has explicit False.
            if provider in {"groq", "gemini"} and provider in providers:
                if providers.get(provider) is False:
                    reasons.append("PROVIDER_UNAVAILABLE")

            if provider == "local" and installed_known and model:
                if model.casefold() not in installed:
                    reasons.append("LOCAL_MODEL_NOT_INSTALLED")

            if candidate.supported_tasks:
                supported = {_name(x) for x in candidate.supported_tasks}
                if _name(req.task_type) not in supported:
                    reasons.append("TASK_UNSUPPORTED")

            required_ctx = max(0, _int(req.required_context_tokens))
            if required_ctx and candidate.context_window is not None:
                if required_ctx > max(0, _int(candidate.context_window)):
                    reasons.append("CONTEXT_WINDOW_TOO_SMALL")

            if candidate.min_ram_gb is not None and safe_ram_available_gb > 0:
                if _float(candidate.min_ram_gb) > safe_ram_available_gb:
                    reasons.append("INSUFFICIENT_RAM_HEADROOM")

            if (
                candidate.uses_local_gpu
                and candidate.min_vram_mb is not None
                and vram_total_mb > 0
            ):
                if _float(candidate.min_vram_mb) > safe_vram_free_mb:
                    reasons.append("INSUFFICIENT_VRAM_HEADROOM")

            if reasons:
                rejected.append(
                    EligibilityRejectionV3(
                        provider=provider,
                        model=model,
                        reason_codes=tuple(dict.fromkeys(reasons)),
                    )
                )
            else:
                eligible.append(candidate)

        fail_closed = len(eligible) == 0
        return EligibilityResultV3(
            schema=SCHEMA,
            version=VERSION,
            eligible=tuple(eligible),
            rejected=tuple(rejected),
            fail_closed=fail_closed,
            error_code="NO_ELIGIBLE_CANDIDATES" if fail_closed else None,
            facts={
                "local_required": local_required,
                "network_allowed": bool(req.network_allowed),
                "installed_local_models_known": installed_known,
                "ram_available_gb": ram_available_gb,
                "safe_ram_available_gb": safe_ram_available_gb,
                "vram_total_mb": vram_total_mb,
                "vram_used_mb": vram_used_mb,
                "raw_vram_free_mb": raw_vram_free_mb,
                "xtts_vram_reserve_mb": xtts_reserve,
                "safe_vram_free_mb": safe_vram_free_mb,
            },
        )
