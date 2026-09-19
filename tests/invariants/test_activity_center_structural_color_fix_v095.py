from __future__ import annotations
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from core.version import AURA_VERSION

UI_ROOT=Path(os.environ.get("LOCALAPPDATA",""))/"AURA"/"ui"/"v0.7.2.2-rc4.2"

js_files=[
    ROOT/"aura-p081-event-watchers.js",
    UI_ROOT/"src"/"aura-p081-event-watchers.js",
    UI_ROOT/"src"/"assets"/"aura-p081-event-watchers.js",
    UI_ROOT/"dist"/"assets"/"aura-p081-event-watchers.js",
]

css_candidates=[
    ROOT/"aura-p081-event-watchers.css",
    UI_ROOT/"src"/"aura-p081-event-watchers.css",
    UI_ROOT/"src"/"assets"/"aura-p081-event-watchers.css",
    UI_ROOT/"dist"/"assets"/"aura-p081-event-watchers.css",
]
css_files=[p for p in css_candidates if p.is_file()]

assert AURA_VERSION=="0.9.5"

for path in js_files:
    text=path.read_text(encoding="utf-8-sig",errors="replace")
    assert "// --- AURA V0.9.5 D2 R5 ACTIVITY CENTER THEME START ---" not in text
    assert "// --- AURA V0.9.5 D2 R7 ZERO PURPLE UI MATCH START ---" not in text
    assert "aura-p095-activity-center-exact-theme" not in text
    assert "aura-p095-r7-zero-purple-ui-match" not in text
    assert "aura-ac-surface" not in text
    assert "aura-ac-card" not in text
    assert "legacy.remove()" in text
    assert "AuraEventWatchers" in text

assert css_files
for path in css_files:
    text=path.read_text(encoding="utf-8-sig",errors="replace")
    assert "/* --- AURA V0.9.5 D2 R9 ACTIVITY CENTER STRUCTURAL THEME START --- */" in text
    assert "/* --- AURA V0.9.5 D2 R9 ACTIVITY CENTER STRUCTURAL THEME END --- */" in text
    assert ".aura-p081-panel" in text
    assert ".aura-p081-family.active" in text
    assert ".aura-p081-overview strong" in text
    assert ".aura-p082-engine-strip" in text
    assert '.aura-p081-event[data-status="new"]' in text
    assert "rgba(113, 224, 255, 0.16)" in text

print("[PASS] AURA v0.9.5 Activity Center structural color fix invariant")
print("[PASS] broad runtime theming removed")
print("[PASS] exact P0.8.1 CSS scope retained")
