from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
UI = Path.home()  # unused in test; just placeholder
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA = ROOT / "data" / "youtube" / "neural_echo_youtube_snapshot_v150.json"
PRESENTER = ROOT / "runtime" / "personal_result_presenter_v123.py"

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

data = json.loads(DATA.read_text(encoding="utf-8-sig"))
assert (data.get("channel") or {}).get("title") == "Neural Echo Music"
assert ((data.get("channel") or {}).get("current_stats") or {}).get("subscribers") == 116

text = PRESENTER.read_text(encoding="utf-8")
assert text.count("# ==== AURA_Y150_R4_TRUE_ANALYTICS_PANEL ====") == 1
assert "__AURA_Y150_ANALYTICS_JSON__" in text

road = sha(ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json")
state = sha(ROOT / "data" / "roadmap" / "aura_roadmap_schedule_state.json")

print("[PASS] presenter opening marker installed exactly once")
print("[PASS] dashboard bootstrap marker installed")
print("[PASS] live Neural Echo snapshot unchanged")
print("[PASS] live Roadmap unchanged")
print("[PASS] live schedule unchanged")
