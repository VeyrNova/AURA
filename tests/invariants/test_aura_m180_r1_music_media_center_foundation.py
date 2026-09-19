from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_music_media_center_v180 import (
    MusicMediaCenter,
    capability_snapshot,
)

ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


road_sha = sha(ROADMAP)

caps = capability_snapshot()
assert caps["catalog_summary"] is True
assert caps["catalog_search"] is True
assert caps["smart_queue"] is True
assert caps["playlist_proposal"] is True
assert caps["playback_intent_plan"] is True
assert caps["real_player_control"] is False
assert caps["filesystem_delete"] is False
assert caps["filesystem_move"] is False
assert caps["filesystem_rename"] is False
assert caps["external_playlist_write"] is False
assert caps["external_account_mutation"] is False
assert caps["explicit_confirmation_required_for_future_player_mutation"] is True

items = [
    {
        "media_id": "track-1",
        "title": "Neon Rain",
        "artist": "Neural Echo",
        "media_type": "audio",
        "genre": "Nu Metal Shoegaze",
        "album": "Low Signals Archive",
        "duration_seconds": 249,
        "rating": 4.8,
        "play_count": 12,
        "path": r"C:\Music\Neon Rain.wav",
    },
    {
        "media_id": "track-2",
        "title": "Blue Static",
        "artist": "Neural Echo",
        "media_type": "audio",
        "genre": "Shoegaze",
        "album": "Low Signals Archive",
        "duration_seconds": 289,
        "rating": 4.5,
        "play_count": 8,
        "path": r"C:\Music\Blue Static.wav",
    },
    {
        "media_id": "video-1",
        "title": "Under My Skin Visualizer",
        "artist": "Neural Echo",
        "media_type": "video",
        "genre": "Alt Metal",
        "duration_seconds": 220,
        "rating": 4.3,
        "play_count": 3,
        "path": r"C:\Videos\Under My Skin.mp4",
    },
]

center = MusicMediaCenter(items)

summary = center.catalog_summary()
assert summary == {
    "schema": "aura.music-media-center.v180",
    "kind": "catalog_summary",
    "total": 3,
    "audio": 2,
    "video": 1,
    "artists": 1,
    "genres": 3,
    "read_only": True,
}

search = center.search("neural echo", media_type="audio")
assert search["count"] == 2
assert all(x["media_type"] == "audio" for x in search["items"])

queue = center.smart_queue(
    genre="shoegaze",
    media_type="audio",
    max_items=2,
)
assert queue["count"] == 2
assert queue["items"][0]["queue_score"] > 0
assert queue["explainable"] is True
assert queue["player_mutation_performed"] is False

playlist = center.playlist_proposal(
    "Neural Echo Focus",
    query="neural echo",
    max_items=10,
)
assert playlist["count"] == 3
assert playlist["requires_explicit_confirmation"] is True
assert playlist["external_playlist_write_performed"] is False
assert playlist["filesystem_mutation_performed"] is False

intent = center.playback_intent("track-1", action="play")
assert intent["state"] == "approval_required"
assert intent["requires_explicit_confirmation"] is True
assert intent["player_mutation_performed"] is False
assert intent["external_account_mutation_performed"] is False

assert sha(ROADMAP) == road_sha

print("[PASS] normalized audio/video catalog")
print("[PASS] catalog summary")
print("[PASS] music/video search filters")
print("[PASS] explainable smart queue")
print("[PASS] playlist proposal without external write")
print("[PASS] playback intent stops at approval_required")
print("[PASS] no real player mutation")
print("[PASS] no filesystem delete/move/rename")
print("[PASS] no external media-account mutation")
print("[PASS] live Roadmap unchanged")
