from __future__ import annotations

"""AURA Intelligence Gateway v3 — isolated orchestration layer.

This module coordinates the v3 decision stack and delegates actual generation to
an injected Fabric executor. It intentionally contains NO provider HTTP code,
NO provider SDK, NO hardware probing, and NO model lifecycle operations.

Execution ownership remains with the existing AURA Fabric production service
(GatewayService.execute + aura_fabric_resilience + live provider adapters).

The future Fabric binding is expected to implement:
    fabric_executor(execution_payload, selected_route) -> mapping-like result

where selected_route contains at least provider/model. The binding may adapt the
opaque execution_payload into AURA's existing CanonicalRequest and route slug.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping, Sequence

from runtime.aura_decision_trace_v3 import DecisionTraceV3
from runtime.aura_eligibility_filter_v3 import (
    EligibilityFilterV3,
    EligibilityRequestV3,
    RouteCandidateV3,
)
from runtime.aura_model_policy_engine_v3 import (
    ModelPolicyEngineV3,
    ModelPolicyRequest,
)
from runtime.aura_model_switch_gate_v3 import (
    ModelSwitchGateV3,
    ModelSwitchRequestV3,
    ModelSwitchSessionStateV3,
    RouteIdentityV3,
)
from runtime.aura_provider_health_registry_v3 import ProviderHealthRegistryV3

SCHEMA = "aura.intelligence_gateway.v3"
VERSION = "3.0.0"


@dataclass(frozen=True)
class IntelligenceGatewayRequestV3:
    execution_payload: Any
    candidates: tuple[RouteCandidateV3, ...]
    policy_request: ModelPolicyRequest
    session_state: ModelSwitchSessionStateV3 = field(
        default_factory=ModelSwitchSessionStateV3
    )
    correlation_id: str = ""
    network_allowed: bool = True
    required_context_tokens: int = 0
    preserve_xtts: bool = True
    xtts_hot: bool = False
    xtts_vram_reserve_mb: float = 0.0
    ram_reserve_gb: float = 0.0
    switch_advantage_score: float = 0.0
    switch_penalty: float = 0.0
    proposed_warm: bool = False
    warm_bonus: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IntelligenceGatewayResultV3:
    schema: str
    version: str
    ok: bool
    blocked: bool
    text: str
    provider: str
    model: str
    error_code: str
    finish_reason: str
    fallback_count: int
    execution: Mapping[str, Any]
    trace: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _provider(value: Any) -> str:
    return str(value or "").strip().casefold()


def _model(value: Any) -> str:
    return str(value or "").strip()


def _route_key(provider: Any, model: Any) -> tuple[str, str]:
    return (_provider(provider), _model(model).casefold())


def _candidate_key(candidate: RouteCandidateV3) -> tuple[str, str]:
    return _route_key(candidate.provider, candidate.model)


def _policy_route(raw: Mapping[str, Any] | None) -> tuple[str, str]:
    if not isinstance(raw, Mapping):
        return ("", "")
    return _route_key(raw.get("provider"), raw.get("model"))


def _result_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "as_dict") and callable(value.as_dict):
        raw = value.as_dict()
        return dict(raw) if isinstance(raw, Mapping) else {"value": raw}
    if hasattr(value, "__dict__"):
        return {
            str(k): v
            for k, v in vars(value).items()
            if not str(k).startswith("_")
        }
    return {"value": value}


class IntelligenceGatewayV3:
    """Orchestrate AURA v3 decisions, then delegate one execution to Fabric."""

    def __init__(
        self,
        *,
        capability_service: Any,
        fabric_executor: Callable[[Any, Mapping[str, Any]], Any],
        model_policy: ModelPolicyEngineV3 | None = None,
        eligibility_filter: EligibilityFilterV3 | None = None,
        switch_gate: ModelSwitchGateV3 | None = None,
        provider_health: ProviderHealthRegistryV3 | None = None,
    ) -> None:
        if capability_service is None:
            raise ValueError("capability_service is required")
        if not callable(fabric_executor):
            raise TypeError("fabric_executor must be callable")

        self.capabilities = capability_service
        self.fabric_executor = fabric_executor
        self.model_policy = model_policy or ModelPolicyEngineV3(capability_service)
        self.eligibility_filter = eligibility_filter or EligibilityFilterV3()
        self.switch_gate = switch_gate or ModelSwitchGateV3()
        self.provider_health = provider_health or ProviderHealthRegistryV3()

    def execute(
        self,
        request: IntelligenceGatewayRequestV3,
    ) -> IntelligenceGatewayResultV3:
        if not isinstance(request, IntelligenceGatewayRequestV3):
            raise TypeError("request must be IntelligenceGatewayRequestV3")

        policy_req = request.policy_request
        trace = DecisionTraceV3(
            correlation_id=request.correlation_id,
            task_type=policy_req.task_type,
            mode=policy_req.mode,
            privacy=policy_req.privacy,
            voice_output=policy_req.voice_output,
            streaming=policy_req.streaming,
            metadata=request.metadata,
        )

        resource = self.capabilities.resource_snapshot(
            include_ollama=False,
            force_gpu=False,
        )
        model_catalog = self.capabilities.local_model_catalog(force=False)

        installed_local_models: tuple[str, ...] = ()
        if isinstance(model_catalog, Mapping) and model_catalog.get("available") is not False:
            raw_models = model_catalog.get("data", ())
            if isinstance(raw_models, Sequence) and not isinstance(raw_models, (str, bytes)):
                names = []
                for item in raw_models:
                    if isinstance(item, Mapping):
                        name = str(item.get("name") or item.get("model") or "").strip()
                        if name:
                            names.append(name)
                installed_local_models = tuple(names)

        health_map: dict[str, bool] = {}
        health_details: dict[str, Mapping[str, Any]] = {}
        for candidate in request.candidates:
            provider = _provider(candidate.provider)
            if not provider or provider == "local":
                continue
            snap = self.provider_health.snapshot(provider)
            health_map[provider] = bool(snap.eligible)
            health_details[provider] = snap.as_dict()

        eligibility = self.eligibility_filter.filter(
            request.candidates,
            EligibilityRequestV3(
                task_type=policy_req.task_type,
                mode=policy_req.mode,
                privacy=policy_req.privacy,
                required_context_tokens=max(0, int(request.required_context_tokens)),
                network_allowed=bool(request.network_allowed),
                preserve_xtts=bool(request.preserve_xtts),
                xtts_hot=bool(request.xtts_hot),
                xtts_vram_reserve_mb=max(0.0, float(request.xtts_vram_reserve_mb)),
                ram_reserve_gb=max(0.0, float(request.ram_reserve_gb)),
            ),
            resource_snapshot=resource,
            provider_availability={"available": True, "data": health_map},
            installed_local_models=installed_local_models,
        )

        trace.add_event(
            stage="eligibility",
            outcome="blocked" if eligibility.fail_closed else "filtered",
            reason_codes=(
                ("NO_ELIGIBLE_CANDIDATES",)
                if eligibility.fail_closed
                else ("ELIGIBLE_CANDIDATES_AVAILABLE",)
            ),
            rejected=tuple(
                {
                    "provider": item.provider,
                    "model": item.model,
                    "reason_codes": item.reason_codes,
                }
                for item in eligibility.rejected
            ),
            metadata={
                "eligible_count": len(eligibility.eligible),
                "candidate_count": len(request.candidates),
                "health": health_details,
            },
        )

        if eligibility.fail_closed:
            completed = trace.complete(
                status="blocked",
                finish_reason="eligibility",
                metadata={"error_code": "NO_ELIGIBLE_CANDIDATES"},
            )
            return IntelligenceGatewayResultV3(
                schema=SCHEMA,
                version=VERSION,
                ok=False,
                blocked=True,
                text="",
                provider="",
                model="",
                error_code="NO_ELIGIBLE_CANDIDATES",
                finish_reason="eligibility",
                fallback_count=0,
                execution={},
                trace=completed.as_dict(),
            )

        decision = self.model_policy.decide(policy_req)
        trace.add_event(
            stage="model_policy",
            outcome="blocked" if decision.blocked else "selected",
            selected_provider=str(decision.primary.get("provider") or ""),
            selected_model=str(decision.primary.get("model") or ""),
            reason_codes=decision.reason_codes,
            metadata={
                "fallback_count": len(decision.fallback_chain),
                "blocked": decision.blocked,
            },
        )

        if decision.blocked:
            completed = trace.complete(
                status="blocked",
                finish_reason="model_policy",
                metadata={"error_code": "MODEL_POLICY_BLOCKED"},
            )
            return IntelligenceGatewayResultV3(
                schema=SCHEMA,
                version=VERSION,
                ok=False,
                blocked=True,
                text="",
                provider="",
                model="",
                error_code="MODEL_POLICY_BLOCKED",
                finish_reason="model_policy",
                fallback_count=0,
                execution={},
                trace=completed.as_dict(),
            )

        eligible = tuple(eligibility.eligible)
        proposed = self._select_policy_candidate(decision, eligible)
        if proposed is None:
            trace.add_event(
                stage="model_policy",
                outcome="blocked_no_eligible_policy_route",
                reason_codes=("POLICY_NO_ELIGIBLE_ROUTE",),
            )
            completed = trace.complete(
                status="blocked",
                finish_reason="policy_eligibility_intersection",
                metadata={"error_code": "POLICY_NO_ELIGIBLE_ROUTE"},
            )
            return IntelligenceGatewayResultV3(
                schema=SCHEMA,
                version=VERSION,
                ok=False,
                blocked=True,
                text="",
                provider="",
                model="",
                error_code="POLICY_NO_ELIGIBLE_ROUTE",
                finish_reason="policy_eligibility_intersection",
                fallback_count=0,
                execution={},
                trace=completed.as_dict(),
            )

        current = request.session_state.current
        eligible_keys = {_candidate_key(item) for item in eligible}
        current_eligible = (
            current is None
            or self._route_identity_is_eligible(current, eligible)
        )

        current_unhealthy = False
        if current is not None and _provider(current.provider) != "local":
            current_unhealthy = not self.provider_health.snapshot(current.provider).eligible

        gate = self.switch_gate.evaluate(
            request.session_state,
            ModelSwitchRequestV3(
                proposed=RouteIdentityV3(proposed.provider, proposed.model),
                current_eligible=current_eligible,
                proposed_eligible=_candidate_key(proposed) in eligible_keys,
                explicit_user_preference=bool(policy_req.preferred_provider),
                hard_constraint_requires_switch=(
                    not current_eligible
                    and (policy_req.mode == "local_only" or policy_req.privacy == "local_required")
                ),
                current_unhealthy=current_unhealthy,
                proposed_warm=bool(request.proposed_warm),
                advantage_score=float(request.switch_advantage_score),
                switch_penalty=max(0.0, float(request.switch_penalty)),
                warm_bonus=max(0.0, float(request.warm_bonus)),
            ),
        )

        selected = self._candidate_for_identity(gate.selected, eligible)
        if selected is None:
            trace.add_event(
                stage="model_switch_gate",
                outcome="blocked",
                reason_codes=("SWITCH_GATE_SELECTED_NON_ELIGIBLE_ROUTE",),
            )
            completed = trace.complete(
                status="blocked",
                finish_reason="model_switch_gate",
                metadata={"error_code": "SWITCH_GATE_SELECTED_NON_ELIGIBLE_ROUTE"},
            )
            return IntelligenceGatewayResultV3(
                schema=SCHEMA,
                version=VERSION,
                ok=False,
                blocked=True,
                text="",
                provider="",
                model="",
                error_code="SWITCH_GATE_SELECTED_NON_ELIGIBLE_ROUTE",
                finish_reason="model_switch_gate",
                fallback_count=0,
                execution={},
                trace=completed.as_dict(),
            )

        trace.add_event(
            stage="model_switch_gate",
            outcome="switch" if gate.allow_switch else "keep_current",
            selected_provider=selected.provider,
            selected_model=selected.model,
            reason_codes=gate.reason_codes,
            metadata={
                "effective_advantage": gate.effective_advantage,
                "threshold": gate.threshold,
            },
        )

        execution_candidates = self._ordered_execution_candidates(
            decision,
            eligible,
            selected,
        )
        gateway_attempts: list[dict[str, Any]] = []
        last_execution: dict[str, Any] = {}
        last_provider = _provider(selected.provider)
        last_model = _model(selected.model)
        last_error_code = ""
        last_finish_reason = "error"
        last_error_chain: list[dict[str, Any]] = []
        last_nested_fallback_count = 0

        for gateway_attempt_index, execution_candidate in enumerate(execution_candidates):
            selected_route = {
                "provider": _provider(execution_candidate.provider),
                "model": _model(execution_candidate.model),
                "metadata": dict(execution_candidate.metadata or {}),
            }

            if gateway_attempt_index > 0:
                # Runtime recovery is still constrained to an already-eligible,
                # policy-compatible route. Emit a final switch-stage event so
                # downstream session state reflects the route that actually
                # completed the turn.
                trace.add_event(
                    stage="model_switch_gate",
                    outcome="runtime_fallback",
                    selected_provider=selected_route["provider"],
                    selected_model=selected_route["model"],
                    reason_codes=("EXECUTION_FAILURE_FALLBACK",),
                    metadata={
                        "gateway_fallback_index": gateway_attempt_index,
                        "gateway_candidate_count": len(execution_candidates),
                    },
                )

            try:
                execution_raw = self.fabric_executor(
                    request.execution_payload,
                    selected_route,
                )
                execution = _result_mapping(execution_raw)
            except Exception as exc:
                provider = selected_route["provider"]
                error_code = self._exception_code(exc)
                if provider and provider != "local":
                    self.provider_health.record_failure(
                        provider,
                        error_code=error_code,
                        metadata={
                            "exception_type": type(exc).__name__,
                            "source": "fabric_executor_exception",
                        },
                    )

                attempt_record = {
                    "gateway_attempt": gateway_attempt_index + 1,
                    "provider": selected_route["provider"],
                    "model": selected_route["model"],
                    "ok": False,
                    "error_code": error_code,
                    "exception_type": type(exc).__name__,
                }
                gateway_attempts.append(attempt_record)
                last_provider = selected_route["provider"]
                last_model = selected_route["model"]
                last_error_code = error_code
                last_finish_reason = "exception"
                last_error_chain.append(dict(attempt_record))

                trace.add_event(
                    stage="gateway",
                    outcome="exception",
                    selected_provider=selected_route["provider"],
                    selected_model=selected_route["model"],
                    reason_codes=("FABRIC_EXECUTOR_EXCEPTION",),
                    metadata={
                        "exception_type": type(exc).__name__,
                        "gateway_attempt": gateway_attempt_index + 1,
                        "gateway_candidate_count": len(execution_candidates),
                    },
                )
                continue

            ok = bool(execution.get("ok", True))
            provider = _provider(
                execution.get("provider_id")
                or execution.get("provider")
                or selected_route["provider"]
            )
            model = _model(
                execution.get("routed_model")
                or execution.get("model")
                or selected_route["model"]
            )
            latency_ms = execution.get("latency_ms")
            error_code = str(execution.get("error_code") or "").strip().casefold()
            nested_fallback_count = max(
                0,
                int(
                    execution.get("fallback_count")
                    or execution.get("failover_count")
                    or 0
                ),
            )

            if provider and provider != "local":
                if ok:
                    self.provider_health.record_success(
                        provider,
                        latency_ms=latency_ms,
                    )
                else:
                    self.provider_health.record_failure(
                        provider,
                        error_code=error_code or "unknown_error",
                        retry_after_seconds=execution.get("retry_after_seconds"),
                        latency_ms=latency_ms,
                        metadata={"source": "fabric_executor_result"},
                    )

            attempt_record = {
                "gateway_attempt": gateway_attempt_index + 1,
                "provider": provider,
                "model": model,
                "ok": ok,
                "error_code": error_code,
                "nested_fallback_count": nested_fallback_count,
            }
            gateway_attempts.append(attempt_record)

            trace.add_event(
                stage="gateway",
                outcome="success" if ok else "failed",
                selected_provider=provider,
                selected_model=model,
                reason_codes=(
                    ("FABRIC_EXECUTION_OK",)
                    if ok
                    else ("FABRIC_EXECUTION_FAILED",)
                ),
                latency_ms=latency_ms,
                metadata={
                    "gateway_attempt": gateway_attempt_index + 1,
                    "gateway_candidate_count": len(execution_candidates),
                    "nested_fallback_count": nested_fallback_count,
                    "attempt_count": len(execution.get("attempts") or ()),
                },
            )

            last_execution = dict(execution)
            last_provider = provider
            last_model = model
            last_error_code = error_code
            last_finish_reason = str(
                execution.get("finish_reason")
                or ("stop" if ok else "error")
            )
            last_nested_fallback_count = nested_fallback_count
            if not ok:
                last_error_chain.extend(
                    tuple(execution.get("error_chain") or ())
                )
                if not execution.get("error_chain"):
                    last_error_chain.append(dict(attempt_record))
                continue

            gateway_fallback_count = gateway_attempt_index
            total_fallback_count = gateway_fallback_count + nested_fallback_count

            normalized_execution = dict(execution)
            normalized_execution["gateway_attempts"] = list(gateway_attempts)
            normalized_execution["gateway_failover_count"] = gateway_fallback_count
            normalized_execution["fallback_count"] = total_fallback_count
            normalized_execution["failover_count"] = total_fallback_count
            normalized_execution["failover_used"] = bool(
                execution.get("failover_used")
                or gateway_fallback_count > 0
                or nested_fallback_count > 0
            )

            text = str(normalized_execution.get("text") or "")
            finish_reason = str(
                normalized_execution.get("finish_reason")
                or "stop"
            )

            trace.add_event(
                stage="gateway",
                outcome="success",
                selected_provider=provider,
                selected_model=model,
                reason_codes=("FABRIC_EXECUTION_OK",),
                latency_ms=latency_ms,
                metadata={
                    "fallback_count": total_fallback_count,
                    "gateway_fallback_count": gateway_fallback_count,
                    "nested_fallback_count": nested_fallback_count,
                    "gateway_attempt_count": len(gateway_attempts),
                    "attempt_count": len(normalized_execution.get("attempts") or ()),
                },
            )
            completed = trace.complete(
                status="completed",
                selected_provider=provider,
                selected_model=model,
                finish_reason=finish_reason,
                fallback_count=total_fallback_count,
                error_chain=tuple(last_error_chain)
                + tuple(normalized_execution.get("error_chain") or ()),
                metadata={"error_code": error_code},
            )
            return IntelligenceGatewayResultV3(
                schema=SCHEMA,
                version=VERSION,
                ok=True,
                blocked=False,
                text=text,
                provider=provider,
                model=model,
                error_code=error_code,
                finish_reason=finish_reason,
                fallback_count=total_fallback_count,
                execution=normalized_execution,
                trace=completed.as_dict(),
            )

        gateway_fallback_count = max(0, len(gateway_attempts) - 1)
        total_fallback_count = gateway_fallback_count + last_nested_fallback_count
        failed_execution = dict(last_execution)
        failed_execution["gateway_attempts"] = list(gateway_attempts)
        failed_execution["gateway_failover_count"] = gateway_fallback_count
        failed_execution["fallback_count"] = total_fallback_count
        failed_execution["failover_count"] = total_fallback_count
        failed_execution["failover_used"] = bool(
            gateway_fallback_count > 0
            or last_nested_fallback_count > 0
            or failed_execution.get("failover_used")
        )

        trace.add_event(
            stage="gateway",
            outcome="failed",
            selected_provider=last_provider,
            selected_model=last_model,
            reason_codes=("FABRIC_EXECUTION_EXHAUSTED",),
            metadata={
                "fallback_count": total_fallback_count,
                "gateway_fallback_count": gateway_fallback_count,
                "nested_fallback_count": last_nested_fallback_count,
                "gateway_attempt_count": len(gateway_attempts),
            },
        )
        completed = trace.complete(
            status="failed",
            selected_provider=last_provider,
            selected_model=last_model,
            finish_reason=last_finish_reason,
            fallback_count=total_fallback_count,
            error_chain=tuple(last_error_chain)
            + tuple(failed_execution.get("error_chain") or ()),
            metadata={"error_code": last_error_code or "executor_error"},
        )
        return IntelligenceGatewayResultV3(
            schema=SCHEMA,
            version=VERSION,
            ok=False,
            blocked=False,
            text=str(failed_execution.get("text") or ""),
            provider=last_provider,
            model=last_model,
            error_code=last_error_code or "executor_error",
            finish_reason=last_finish_reason,
            fallback_count=total_fallback_count,
            execution=failed_execution,
            trace=completed.as_dict(),
        )

    @staticmethod
    def _select_policy_candidate(
        decision: Any,
        eligible: Sequence[RouteCandidateV3],
    ) -> RouteCandidateV3 | None:
        routes = [decision.primary, *tuple(decision.fallback_chain)]
        for raw in routes:
            provider, model = _policy_route(raw)
            if not provider:
                continue
            for candidate in eligible:
                cp, cm = _candidate_key(candidate)
                if cp != provider:
                    continue
                if model and cm != model:
                    continue
                return candidate
        return None

    @staticmethod
    def _ordered_execution_candidates(
        decision: Any,
        eligible: Sequence[RouteCandidateV3],
        selected: RouteCandidateV3,
    ) -> tuple[RouteCandidateV3, ...]:
        """Bounded runtime fallback order.

        The gate-selected exact candidate is always first. Other eligible models
        on that same policy provider are next (needed for local-model recovery),
        followed by routes explicitly present in ModelPolicyEngineV3's primary /
        fallback chain. Exact Fabric route ids are used for de-duplication when
        available so aliases of the same route are never executed twice.
        """
        ordered: list[RouteCandidateV3] = []
        seen: set[tuple[str, ...]] = set()

        def identity(candidate: RouteCandidateV3) -> tuple[str, ...]:
            metadata = dict(candidate.metadata or {})
            exact = str(
                metadata.get("fabric_route_slug")
                or metadata.get("route_slug")
                or metadata.get("fabric_model_id")
                or ""
            ).strip().casefold()
            if exact:
                return ("fabric", exact)
            provider, model = _candidate_key(candidate)
            return ("route", provider, model)

        def add(candidate: RouteCandidateV3) -> None:
            key = identity(candidate)
            if key in seen:
                return
            seen.add(key)
            ordered.append(candidate)

        add(selected)

        # Honor only routes explicitly approved by ModelPolicyEngineV3.
        # EligibilityFilterV3 has already removed ineligible candidates.
        for raw in [decision.primary, *tuple(decision.fallback_chain)]:
            provider, model = _policy_route(raw)
            if not provider:
                continue
            for candidate in eligible:
                cp, cm = _candidate_key(candidate)
                if cp != provider:
                    continue
                if model and cm != model:
                    continue
                add(candidate)

        return tuple(ordered)


    @staticmethod
    def _route_identity_is_eligible(
        route: RouteIdentityV3,
        eligible: Sequence[RouteCandidateV3],
    ) -> bool:
        provider, model = _route_key(route.provider, route.model)
        for candidate in eligible:
            cp, cm = _candidate_key(candidate)
            if cp == provider and (not model or cm == model):
                return True
        return False

    @staticmethod
    def _candidate_for_identity(
        route: RouteIdentityV3,
        eligible: Sequence[RouteCandidateV3],
    ) -> RouteCandidateV3 | None:
        provider, model = _route_key(route.provider, route.model)
        for candidate in eligible:
            cp, cm = _candidate_key(candidate)
            if cp == provider and (not model or cm == model):
                return candidate
        return None

    @staticmethod
    def _exception_code(exc: Exception) -> str:
        name = type(exc).__name__.casefold()
        text = str(exc or "").casefold()
        if "timeout" in name or "timeout" in text:
            return "timeout"
        if "429" in text or "rate" in text and "limit" in text:
            return "rate_limit"
        if "auth" in text or "api key" in text or "apikey" in text:
            return "auth"
        if "connection" in name or "connection" in text:
            return "connection_error"
        return "executor_error"
