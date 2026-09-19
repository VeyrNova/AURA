from __future__ import annotations

from integrations.registry import IntegrationRegistry
from integrations.obsidian_creative import OBSIDIAN_PROVIDER_ID, ObsidianCreativeProvider


def register_obsidian_creative_provider_v140(registry: IntegrationRegistry, *, default_vault=None):
    existing = registry.get_provider(OBSIDIAN_PROVIDER_ID)
    if existing is not None:
        return registry.health_snapshot(OBSIDIAN_PROVIDER_ID)
    return registry.register_provider(ObsidianCreativeProvider(default_vault=default_vault))
