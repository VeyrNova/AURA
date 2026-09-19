from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import runtime.personal_result_presenter_v123 as presenter

PRESENTER = ROOT / "runtime" / "personal_result_presenter_v123.py"
DATA = ROOT / "data" / "youtube" / "neural_echo_youtube_snapshot_v150.json"

text = PRESENTER.read_text(encoding="utf-8")
assert '"title": _marker' in text
assert "AURA_Y150_R4_R2_BOOTSTRAP_IN_RENDERED_TITLE" in text

marker = presenter._aura_y150_r4_dashboard_payload()
assert marker.startswith("__AURA_Y150_ANALYTICS_JSON__:")
encoded = marker.split(":", 1)[1]
decoded = json.loads(base64.b64decode(encoded).decode("utf-8"))

assert decoded["panel_kind"] == "youtube_analytics_dashboard"
assert decoded["channel_title"] == "Neural Echo Music"
assert decoded["kpis"]["subscribers"] == 116
assert decoded["kpis"]["views"] == 56294
assert decoded["kpis"]["videos"] == 87

data = json.loads(DATA.read_text(encoding="utf-8-sig"))
assert ((data.get("channel") or {}).get("current_stats") or {}) == {
    "subscribers": 116,
    "views": 56294,
    "videos": 87,
}

print("[PASS] encoded analytics payload is valid base64 JSON")
print("[PASS] bootstrap payload now lives in rendered title text")
print("[PASS] analytics KPI payload = 116 / 56294 / 87")
print("[PASS] live YouTube snapshot unchanged")
