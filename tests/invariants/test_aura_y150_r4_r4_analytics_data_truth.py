from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import runtime.personal_result_presenter_v123 as presenter

marker = presenter._aura_y150_r4_dashboard_payload()
assert marker.startswith("__AURA_Y150_ANALYTICS_JSON__:")
payload = json.loads(base64.b64decode(marker.split(":",1)[1]).decode("utf-8"))

assert payload["panel_kind"] == "youtube_analytics_dashboard"
assert payload["kpis"]["subscribers"] == 116
assert payload["kpis"]["views"] == 56294
assert payload["kpis"]["videos"] == 87
assert payload["kpis"]["median_retention"] > 0
assert payload["kpis"]["median_views_per_day"] > 0
assert payload["kpis"]["ctr_available"] is False

top = payload["top_videos"]
assert len(top) == 5
assert max(x["score"] for x in top) > 0
assert max(x["views_per_day"] for x in top) > 0
assert max(x["retention"] for x in top) > 0

actions = {x["action"] for x in payload["opportunities"]}
assert actions
assert actions != {"watch"}
assert actions != {"monitor"}

print("[PASS] dashboard uses computed scorecards, not raw snapshot placeholders")
print("[PASS] score > 0")
print("[PASS] views/day > 0")
print("[PASS] retention > 0")
print("[PASS] opportunity actions are not all monitor/watch")
print("[PASS] CTR absence remains truthful")
