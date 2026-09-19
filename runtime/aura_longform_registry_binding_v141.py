from __future__ import annotations

from integrations.registry import IntegrationRegistry
from integrations.longform_revision import LONGFORM_PROVIDER_ID, LongFormRevisionProvider


def register_longform_revision_provider_v141(registry: IntegrationRegistry, *, default_vault=None):
    existing = registry.get_provider(LONGFORM_PROVIDER_ID)
    if existing is not None:
        return registry.health_snapshot(LONGFORM_PROVIDER_ID)
    return registry.register_provider(LongFormRevisionProvider(default_vault=default_vault))
