from __future__ import annotations

from integrations.registry import IntegrationRegistry
from integrations.pc_control import PC_CONTROL_PROVIDER_ID, PcControlWindowsProvider


def register_pc_control_provider_v131(
    registry: IntegrationRegistry,
    *,
    backend=None,
):
    existing = registry.get_provider(PC_CONTROL_PROVIDER_ID)
    if existing is not None:
        return registry.health_snapshot(PC_CONTROL_PROVIDER_ID)
    provider = PcControlWindowsProvider(backend=backend)
    return registry.register_provider(provider)
