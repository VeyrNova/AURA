from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.version import AURA_VERSION
from core.spoken_version import format_spoken_product_version
BASELINE = ROOT / "ci" / "baseline_v094.json"
VISUAL_SYNC = ROOT / "tools" / "sync_product_version_surfaces.py"
assert AURA_VERSION == "0.9.4", AURA_VERSION
assert format_spoken_product_version() == "zero point neuf point quatre"
baseline = json.loads(BASELINE.read_text(encoding="utf-8-sig"))
contract = baseline.get("version_contract") or {}
assert contract.get("product_version") == "0.9.4", contract
assert contract.get("visible_display_version") == "v0.9.4", contract
assert contract.get("spoken_version") == "zero point neuf point quatre", contract
cp = subprocess.run([sys.executable,str(VISUAL_SYNC),"--check","--json"],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding="utf-8",errors="replace")
assert cp.returncode == 0, cp.stdout
data = json.loads(cp.stdout.strip().splitlines()[-1])
assert data.get("display_version") == "v0.9.4", data
assert data.get("stale_hits") == [], data
print("[PASS] AURA v0.9.4 metadata/version contract")
raise SystemExit(0)
