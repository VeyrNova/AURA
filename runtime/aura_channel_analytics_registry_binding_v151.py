from __future__ import annotations

from pathlib import Path
from integrations.registry import IntegrationRegistry
from integrations.channel_analytics_publishing import (
    PROVIDER_ID,
    ChannelAnalyticsPublishingProvider,
)

DEFAULT_SNAPSHOT = Path(r"C:\AURA GPT version\data\youtube\neural_echo_youtube_snapshot_v150.json")


def register_channel_analytics_publishing_provider_v151(
    registry: IntegrationRegistry,
    *,
    snapshot_path=None,
):
    existing = registry.get_provider(PROVIDER_ID)
    if existing is not None:
        return registry.health_snapshot(PROVIDER_ID)
    return registry.register_provider(
        ChannelAnalyticsPublishingProvider(snapshot_path or DEFAULT_SNAPSHOT)
    )
