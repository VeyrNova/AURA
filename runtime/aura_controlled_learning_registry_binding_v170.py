from __future__ import annotations

from integrations.registry import IntegrationRegistry
from integrations.controlled_learning import PROVIDER_ID, ControlledLearningProvider


def register_controlled_learning_provider_v170(
    registry: IntegrationRegistry,
    *,
    store_path=None,
):
    existing = registry.get_provider(PROVIDER_ID)
    if existing is not None:
        return registry.health_snapshot(PROVIDER_ID)
    return registry.register_provider(
        ControlledLearningProvider(store_path=store_path)
    )
