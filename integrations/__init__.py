"""AURA v0.9.0 Personal Integrations architecture package."""
from .registry import (
    INTEGRATION_RESULT_STATUSES,
    IntegrationCapability,
    IntegrationError,
    IntegrationManifest,
    IntegrationMissionToolAdapter,
    IntegrationProvider,
    IntegrationProviderState,
    IntegrationRegistry,
    IntegrationRequest,
    IntegrationResult,
    ProviderRegistrationError,
    UnknownCapabilityError,
    UnknownProviderError,
)

__all__ = [
    "INTEGRATION_RESULT_STATUSES",
    "IntegrationCapability",
    "IntegrationError",
    "IntegrationManifest",
    "IntegrationMissionToolAdapter",
    "IntegrationProvider",
    "IntegrationProviderState",
    "IntegrationRegistry",
    "IntegrationRequest",
    "IntegrationResult",
    "ProviderRegistrationError",
    "UnknownCapabilityError",
    "UnknownProviderError",
]
