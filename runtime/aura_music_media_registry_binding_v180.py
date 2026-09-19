from __future__ import annotations

from integrations.registry import IntegrationRegistry
from integrations.music_media_center import PROVIDER_ID, MusicMediaCenterProvider


def register_music_media_center_provider_v180(
    registry: IntegrationRegistry,
    *,
    index_path=None,
):
    existing = registry.get_provider(PROVIDER_ID)
    if existing is not None:
        return registry.health_snapshot(PROVIDER_ID)
    return registry.register_provider(
        MusicMediaCenterProvider(index_path=index_path)
    )
