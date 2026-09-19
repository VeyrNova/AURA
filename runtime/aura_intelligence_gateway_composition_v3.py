from __future__ import annotations

"""AURA Intelligence Gateway v3 composition factory.

This module performs composition only. It does not create or own a second Fabric
GatewayService. Production service ownership remains in
runtime.aura_conversation_fabric_bridge._get_service().

The production service provider is lazy: building the composition does not
instantiate the Fabric production service. The service is requested only if/when
AuraFabricExecutionBindingV3 actually executes a request.
"""

from dataclasses import dataclass
from typing import Any, Callable

from runtime.aura_eligibility_filter_v3 import EligibilityFilterV3
from runtime.aura_fabric_execution_binding_v3 import AuraFabricExecutionBindingV3
from runtime.aura_intelligence_gateway_v3 import IntelligenceGatewayV3
from runtime.aura_model_policy_engine_v3 import ModelPolicyEngineV3
from runtime.aura_model_switch_gate_v3 import ModelSwitchGateV3
from runtime.aura_provider_health_registry_v3 import ProviderHealthRegistryV3

SCHEMA = "aura.intelligence_gateway_composition.v3"
VERSION = "3.0.0"


@dataclass(frozen=True)
class IntelligenceGatewayCompositionV3:
    gateway: IntelligenceGatewayV3
    binding: AuraFabricExecutionBindingV3
    service_provider_kind: str


def conversation_fabric_service_provider() -> Any:
    """Return the canonical conversation Fabric singleton lazily.

    Import is deliberately local to keep composition construction side-effect
    free and to avoid manufacturing an independent GatewayService.
    """
    from runtime import aura_conversation_fabric_bridge as bridge

    provider = getattr(bridge, "_get_service", None)
    if not callable(provider):
        raise RuntimeError(
            "canonical conversation Fabric service provider _get_service is unavailable"
        )
    return provider()


def compose_intelligence_gateway_v3(
    *,
    capability_service: Any,
    service_provider: Callable[[], Any],
    service_provider_kind: str = "injected",
    model_policy: ModelPolicyEngineV3 | None = None,
    eligibility_filter: EligibilityFilterV3 | None = None,
    switch_gate: ModelSwitchGateV3 | None = None,
    provider_health: ProviderHealthRegistryV3 | None = None,
) -> IntelligenceGatewayCompositionV3:
    """Compose the v3 gateway around an injected Fabric service provider."""
    if capability_service is None:
        raise ValueError("capability_service is required")
    if not callable(service_provider):
        raise TypeError("service_provider must be callable")

    binding = AuraFabricExecutionBindingV3(service_provider=service_provider)
    gateway = IntelligenceGatewayV3(
        capability_service=capability_service,
        fabric_executor=binding,
        model_policy=model_policy,
        eligibility_filter=eligibility_filter,
        switch_gate=switch_gate,
        provider_health=provider_health,
    )
    return IntelligenceGatewayCompositionV3(
        gateway=gateway,
        binding=binding,
        service_provider_kind=str(service_provider_kind or "injected"),
    )


def build_production_intelligence_gateway_v3(
    *,
    capability_service: Any,
    model_policy: ModelPolicyEngineV3 | None = None,
    eligibility_filter: EligibilityFilterV3 | None = None,
    switch_gate: ModelSwitchGateV3 | None = None,
    provider_health: ProviderHealthRegistryV3 | None = None,
) -> IntelligenceGatewayCompositionV3:
    """Compose against the existing conversation Fabric singleton owner.

    This function remains lazy: conversation_fabric_service_provider is passed
    as a callable and is not executed while the composition is built.
    """
    return compose_intelligence_gateway_v3(
        capability_service=capability_service,
        service_provider=conversation_fabric_service_provider,
        service_provider_kind="conversation_fabric_singleton",
        model_policy=model_policy,
        eligibility_filter=eligibility_filter,
        switch_gate=switch_gate,
        provider_health=provider_health,
    )
