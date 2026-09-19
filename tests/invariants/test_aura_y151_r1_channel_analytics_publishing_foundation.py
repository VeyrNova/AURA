from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_channel_analytics_publishing_v151 import (
    ChannelAnalyticsPublishingWorkflows,
    capability_snapshot,
)

ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"
DATA = ROOT / "data" / "youtube" / "neural_echo_youtube_snapshot_v150.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


road_sha = sha(ROADMAP)
data_sha = sha(DATA)

caps = capability_snapshot()
assert caps["external_mutating_capabilities"] == []
assert caps["youtube_upload"] is False
assert caps["youtube_edit"] is False
assert caps["youtube_delete"] is False
assert caps["youtube_comment_reply"] is False
assert caps["explicit_confirmation_required_for_future_publish"] is True
assert caps["canonical_receipt_required_for_future_publish"] is True

data = json.loads(DATA.read_text(encoding="utf-8-sig"))
studio = ChannelAnalyticsPublishingWorkflows(data["videos"])

comparison = studio.compare_formats()
assert comparison["formats"]["short"]["sample_size"] > 0
assert comparison["formats"]["video"]["sample_size"] > 0
assert comparison["formats"]["short"]["median_views_per_day"] > 0
assert comparison["formats"]["video"]["median_retention_percent"] > 0

windows = studio.publishing_windows()
assert windows["count"] > 0
assert windows["windows"][0]["sample_size"] >= 1

matrix = studio.recommendation_matrix()
assert len(matrix["formats"]) == 2
assert matrix["recommended_for_reach"] in {"short", "video"}

mix = studio.editorial_mix(uploads_per_week=3)
assert mix["short_slots"] + mix["long_form_slots"] == 3
assert mix["short_slots"] >= 1
assert mix["long_form_slots"] >= 1

workflow = studio.create_publishing_workflow(
    title="Next Neural Echo upload",
    format="short",
    description="Controlled publishing draft",
    scheduled_for="2026-10-08T18:00:00+02:00",
)
assert workflow["state"] == "approval_required"
assert workflow["requires_explicit_confirmation"] is True
assert workflow["external_mutation_performed"] is False
assert workflow["youtube_upload_performed"] is False
assert "explicit_user_confirmation" in workflow["gates"]
assert "canonical_action_receipt_required" in workflow["gates"]

bad = studio.create_publishing_workflow(
    title="",
    format="unknown",
)
assert bad["state"] == "draft_invalid"
assert bad["validation_errors"]

assert sha(ROADMAP) == road_sha
assert sha(DATA) == data_sha

print("[PASS] Shorts vs long-form comparison")
print("[PASS] historical publishing-window analysis")
print("[PASS] format recommendation matrix")
print("[PASS] balanced editorial mix proposal")
print("[PASS] controlled publishing workflow reaches approval_required only")
print("[PASS] invalid workflow fails before approval gate")
print("[PASS] no YouTube upload/edit/delete/comment mutation")
print("[PASS] explicit confirmation required for any future publishing mutation")
print("[PASS] canonical receipt required for any future publishing mutation")
print("[PASS] live snapshot unchanged")
print("[PASS] live Roadmap unchanged")
