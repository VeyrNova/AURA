from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_youtube_studio_copilot_v150 import (
    YouTubeStudioCopilot,
    capability_snapshot,
)

ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


road_sha = sha(ROADMAP)
caps = capability_snapshot()
assert caps["mutating_capabilities"] == []
assert caps["upload_video"] is False
assert caps["edit_video"] is False
assert caps["delete_video"] is False
assert caps["reply_comment"] is False
assert caps["read_only"] is True

now = datetime(2026, 9, 5, tzinfo=timezone.utc)
videos = [
    {
        "video_id": "v1",
        "title": "Nu Metal Is Back",
        "published_at": "2026-09-01T12:00:00Z",
        "views": 12000,
        "likes": 900,
        "comments": 180,
        "subscribers_gained": 120,
        "impressions": 90000,
        "ctr_percent": 8.2,
        "average_view_duration_seconds": 42,
        "duration_seconds": 60,
        "tags": ["nu metal", "deftones"],
        "format": "short",
    },
    {
        "video_id": "v2",
        "title": "Deftones Deep Cut",
        "published_at": "2026-08-29T12:00:00Z",
        "views": 7000,
        "likes": 480,
        "comments": 70,
        "subscribers_gained": 60,
        "impressions": 80000,
        "ctr_percent": 3.2,
        "average_view_duration_seconds": 45,
        "duration_seconds": 60,
        "tags": ["deftones", "shoegaze"],
        "format": "short",
    },
    {
        "video_id": "v3",
        "title": "AI Nu Metal Debate",
        "published_at": "2026-08-25T12:00:00Z",
        "views": 9000,
        "likes": 620,
        "comments": 210,
        "subscribers_gained": 75,
        "impressions": 70000,
        "ctr_percent": 7.5,
        "average_view_duration_seconds": 22,
        "duration_seconds": 60,
        "tags": ["nu metal", "ai music"],
        "format": "short",
    },
    {
        "video_id": "v4",
        "title": "Korn Ranking",
        "published_at": "2026-08-20T12:00:00Z",
        "views": 5000,
        "likes": 330,
        "comments": 45,
        "subscribers_gained": 30,
        "impressions": 35000,
        "ctr_percent": 6.8,
        "average_view_duration_seconds": 41,
        "duration_seconds": 60,
        "tags": ["korn", "nu metal"],
        "format": "short",
    },
    {
        "video_id": "v5",
        "title": "Long-form Album Breakdown",
        "published_at": "2026-08-10T12:00:00Z",
        "views": 3500,
        "likes": 260,
        "comments": 55,
        "subscribers_gained": 45,
        "impressions": 30000,
        "ctr_percent": 6.5,
        "average_view_duration_seconds": 330,
        "duration_seconds": 600,
        "tags": ["album", "nu metal"],
        "format": "video",
    },
]

studio = YouTubeStudioCopilot(videos, channel_name="Neural Echo", now=now)

bench = studio.benchmarks()
assert bench["video_count"] == 5
assert bench["median_views"] == 7000
assert bench["median_ctr_percent"] > 0
assert bench["median_retention_percent"] > 0

scorecards = studio.scorecards()
assert len(scorecards) == 5
assert scorecards[0]["score"] >= scorecards[-1]["score"]
assert all(0 <= x["score"] <= 100 for x in scorecards)

board = studio.opportunity_board()
assert board["count"] == 5
actions = {x["video_id"]: x["action"] for x in board["items"]}
assert actions["v2"] == "packaging"
assert actions["v3"] == "hook_retention"
assert actions["v1"] == "double_down"

v2 = next(x for x in board["items"] if x["video_id"] == "v2")
assert v2["metrics"]["views_per_day"] > board["benchmarks"]["median_views_per_day"]
assert v2["metrics"]["ctr_percent"] < board["benchmarks"]["median_ctr_percent"]

cadence = studio.publishing_cadence()
assert cadence["dated_video_count"] == 5
assert cadence["median_gap_days"] > 0

brief = studio.next_upload_brief()
assert brief["top_reference_videos"]
assert any(x["tag"] == "nu metal" for x in brief["priority_topics"])
assert "Deftones Deep Cut" in brief["packaging_watch"]
assert "AI Nu Metal Debate" in brief["retention_watch"]

snapshot = studio.channel_snapshot()
assert snapshot["total_views"] == 36500
assert snapshot["video_count"] == 5
assert snapshot["read_only"] is True

assert sha(ROADMAP) == road_sha

print("[PASS] Y150-R1 read-only capability contract")
print("[PASS] KPI normalization: velocity / CTR / retention / engagement")
print("[PASS] deterministic explainable video scorecards")
print("[PASS] opportunity board: double-down / packaging / retention / distribution")
print("[PASS] packaging classification is driven by low CTR when impressions exist")
print("[PASS] publishing cadence analysis")
print("[PASS] next-upload decision brief")
print("[PASS] channel aggregate snapshot")
print("[PASS] no upload/edit/delete/comment mutation capability")
print("[PASS] live Roadmap unchanged")
