from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
import time
from typing import Sequence

class Protocol(str, Enum):
    ANTHROPIC_MESSAGES = "anthropic_messages"
    OPENAI_RESPONSES = "openai_responses"
    OPENAI_CHAT = "openai_chat"
    AURA_NATIVE = "aura_native"

@dataclass(frozen=True)
class ModelCapabilities:
    tools: bool = False
    reasoning: bool = False
    vision: bool = False
    streaming: bool = True
    json_mode: bool = False
    max_context_tokens: int | None = None

@dataclass(frozen=True)
class ModelDescriptor:
    provider_id: str
    model_id: str
    display_name: str
    capabilities: ModelCapabilities = field(default_factory=ModelCapabilities)
    input_cost_per_million: float | None = None
    output_cost_per_million: float | None = None
    local: bool = False
    enabled: bool = True

    @property
    def slug(self) -> str:
        return f"{self.provider_id}/{self.model_id}"

@dataclass(frozen=True)
class ProviderDescriptor:
    provider_id: str
    display_name: str
    protocols: tuple[Protocol, ...]
    models: tuple[ModelDescriptor, ...]
    enabled: bool = True
    data_boundary: str = "cloud"
    priority: int = 100

@dataclass
class HealthState:
    healthy: bool = True
    latency_ms_ewma: float | None = None
    success_ewma: float = 1.0
    consecutive_failures: int = 0
    circuit_open_until: float = 0.0

    def record(self, *, success: bool, latency_ms: float | None = None):
        alpha = 0.25
        sample = 1.0 if success else 0.0
        self.success_ewma = alpha * sample + (1.0 - alpha) * self.success_ewma
        if latency_ms is not None:
            self.latency_ms_ewma = (
                latency_ms if self.latency_ms_ewma is None
                else alpha * latency_ms + (1.0 - alpha) * self.latency_ms_ewma
            )
        if success:
            self.consecutive_failures = 0
            self.healthy = True
            self.circuit_open_until = 0.0
        else:
            self.consecutive_failures += 1
            if self.consecutive_failures >= 3:
                self.healthy = False
                backoff = min(300.0, 5.0 * (2 ** min(self.consecutive_failures - 3, 6)))
                self.circuit_open_until = time.monotonic() + backoff

    def available(self) -> bool:
        if self.healthy:
            return True
        return bool(self.circuit_open_until and time.monotonic() >= self.circuit_open_until)

@dataclass(frozen=True)
class RouteRequest:
    protocol: Protocol
    require_tools: bool = False
    require_reasoning: bool = False
    require_vision: bool = False
    require_streaming: bool = False
    min_context_tokens: int = 0
    prefer_local: bool = False
    max_input_cost_per_million: float | None = None
    max_output_cost_per_million: float | None = None
    preferred_models: tuple[str, ...] = ()
    denied_providers: tuple[str, ...] = ()

@dataclass(frozen=True)
class RouteCandidate:
    slug: str
    score: float
    reasons: tuple[str, ...]

@dataclass(frozen=True)
class RouteDecision:
    primary: RouteCandidate
    fallbacks: tuple[RouteCandidate, ...]
    considered: int

class FabricRegistry:
    def __init__(self):
        self._providers: dict[str, ProviderDescriptor] = {}
        self._health: dict[str, HealthState] = {}
        self._aliases: dict[str, tuple[str, ...]] = {}

    def register_provider(self, provider: ProviderDescriptor):
        if not provider.provider_id.strip():
            raise ValueError("provider_id is required")
        self._providers[provider.provider_id] = provider
        for model in provider.models:
            if model.provider_id != provider.provider_id:
                raise ValueError(f"model/provider mismatch: {model.slug}")
            self._health.setdefault(model.slug, HealthState())

    def set_alias(self, alias: str, slugs: Sequence[str]):
        clean = tuple(x.strip() for x in slugs if x.strip())
        if not alias.strip() or not clean:
            raise ValueError("alias and at least one model are required")
        self._aliases[alias.strip()] = clean

    def resolve_alias(self, alias_or_slug: str) -> tuple[str, ...]:
        return self._aliases.get(alias_or_slug, (alias_or_slug,))

    def providers(self) -> tuple[ProviderDescriptor, ...]:
        return tuple(self._providers.values())

    def models(self) -> tuple[ModelDescriptor, ...]:
        out = []
        for p in self._providers.values():
            out.extend(p.models)
        return tuple(out)

    def health(self, slug: str) -> HealthState:
        return self._health.setdefault(slug, HealthState())

    def record_result(self, slug: str, *, success: bool, latency_ms: float | None = None):
        self.health(slug).record(success=success, latency_ms=latency_ms)

    def route(self, request: RouteRequest) -> RouteDecision:
        candidates = []
        preferred = {slug: i for i, slug in enumerate(request.preferred_models)}
        denied = set(request.denied_providers)

        for provider in self._providers.values():
            if not provider.enabled or provider.provider_id in denied:
                continue
            if request.protocol not in provider.protocols and Protocol.AURA_NATIVE not in provider.protocols:
                continue

            for model in provider.models:
                if not model.enabled:
                    continue
                # AFG: an explicit model or alias is a routing boundary, not
                # merely a score hint. This keeps direct Gemini on Gemini and
                # prevents routes outside the requested alias from leaking in.
                if preferred and model.slug not in preferred:
                    continue
                c = model.capabilities
                if request.require_tools and not c.tools:
                    continue
                if request.require_reasoning and not c.reasoning:
                    continue
                if request.require_vision and not c.vision:
                    continue
                if request.require_streaming and not c.streaming:
                    continue
                if request.min_context_tokens and (c.max_context_tokens is None or c.max_context_tokens < request.min_context_tokens):
                    continue
                if request.max_input_cost_per_million is not None and (
                    model.input_cost_per_million is None or model.input_cost_per_million > request.max_input_cost_per_million
                ):
                    continue
                if request.max_output_cost_per_million is not None and (
                    model.output_cost_per_million is None or model.output_cost_per_million > request.max_output_cost_per_million
                ):
                    continue

                h = self.health(model.slug)
                if not h.available():
                    continue

                score = 1000.0 - provider.priority
                reasons = [f"provider_priority={provider.priority}"]

                if model.slug in preferred:
                    bonus = max(0, 200 - preferred[model.slug] * 20)
                    score += bonus
                    reasons.append(f"preferred+{bonus}")

                if request.prefer_local and model.local:
                    score += 160
                    reasons.append("local+160")
                elif request.prefer_local and not model.local:
                    score -= 80
                    reasons.append("cloud-80")

                score += h.success_ewma * 120
                reasons.append(f"success={h.success_ewma:.3f}")

                if h.latency_ms_ewma is not None:
                    latency_penalty = min(180.0, math.log10(max(1.0, h.latency_ms_ewma)) * 45.0)
                    score -= latency_penalty
                    reasons.append(f"latency-{latency_penalty:.1f}")

                if model.input_cost_per_million is not None:
                    score -= min(80.0, model.input_cost_per_million * 2.0)
                if model.output_cost_per_million is not None:
                    score -= min(100.0, model.output_cost_per_million * 1.5)

                candidates.append(RouteCandidate(model.slug, round(score, 3), tuple(reasons)))

        candidates.sort(key=lambda x: (-x.score, x.slug))
        if not candidates:
            raise LookupError("No AURA Fabric Gateway route satisfies the request")
        return RouteDecision(candidates[0], tuple(candidates[1:4]), len(candidates))

GATEWAY_CONTRACT = {
    "name": "AURA Fabric Gateway",
    "schema": "aura.fabric-gateway.contract.v1",
    "clean_room": True,
    "external_code_dependency": False,
    "endpoints_planned": (
        "/health",
        "/ready",
        "/v1/models",
        "/v1/messages",
        "/v1/responses",
        "/v1/chat/completions",
    ),
    "native_improvements": (
        "capability-aware routing",
        "health-weighted adaptive routing",
        "automatic circuit breaker and bounded backoff",
        "local-first/data-boundary preference",
        "cost ceilings",
        "model aliases and ordered fallbacks",
        "per-workspace policy gates",
        "transactional developer actions owned by AURA",
        "provider-neutral contracts",
    ),
}
