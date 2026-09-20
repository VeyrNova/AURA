import os
from pathlib import Path
from integrations.youtube_studio_copilot import YOUTUBE_PROVIDER_ID,YouTubeStudioCopilotProvider
DEFAULT=str(Path(os.environ.get("AURA_ROOT") or Path(__file__).resolve().parents[1]).resolve() / "data" / "youtube" / "neural_echo_youtube_snapshot_v150.json")
def register_youtube_studio_copilot_provider_v150(registry,*,snapshot_path=None):
 existing=registry.get_provider(YOUTUBE_PROVIDER_ID)
 if existing is not None:return registry.health_snapshot(YOUTUBE_PROVIDER_ID)
 return registry.register_provider(YouTubeStudioCopilotProvider(snapshot_path or DEFAULT))
