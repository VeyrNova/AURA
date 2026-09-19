from __future__ import annotations
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from core.version import AURA_VERSION

UI_ROOT=Path(os.environ.get("LOCALAPPDATA",""))/"AURA"/"ui"/"v0.7.2.2-rc4.2"
files=[
    ROOT/"aura-p081-event-watchers.js",
    UI_ROOT/"src"/"aura-p081-event-watchers.js",
    UI_ROOT/"src"/"assets"/"aura-p081-event-watchers.js",
    UI_ROOT/"dist"/"assets"/"aura-p081-event-watchers.js",
]

assert AURA_VERSION=="0.9.4"

for path in files:
    text=path.read_text(encoding="utf-8-sig",errors="replace")
    assert "// --- AURA V0.9.5 D2 R7 ZERO PURPLE UI MATCH START ---" in text
    assert "// --- AURA V0.9.5 D2 R7 ZERO PURPLE UI MATCH END ---" in text
    assert "aura-p095-r7-zero-purple-ui-match" in text
    assert "purpleRGB" in text
    assert "containsPurple" in text
    assert "#030b14" in text
    assert "#051522" in text
    assert "#071a28" in text
    assert "#55dcff" in text
    assert 'button[data-module="activity-center"]' in text
    assert "aura:activity-center-opened" in text

print("[PASS] AURA v0.9.5 Activity Center zero-purple UI match invariant")
