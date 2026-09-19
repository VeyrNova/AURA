from __future__ import annotations
import os
from pathlib import Path

UI = Path(os.environ["LOCALAPPDATA"]) / "AURA" / "ui" / "v0.7.2.2-rc4.2"

js_files = [
    UI / "src" / "aura-v123-personal-results-web.js",
    UI / "src" / "assets" / "aura-v123-personal-results-web.js",
    UI / "dist" / "assets" / "aura-v123-personal-results-web.js",
]
css_files = [
    UI / "src" / "aura-v123-personal-results-web.css",
    UI / "src" / "assets" / "aura-v123-personal-results-web.css",
    UI / "dist" / "assets" / "aura-v123-personal-results-web.css",
]
for p in js_files + css_files:
    assert p.is_file(), p

js = [p.read_text(encoding="utf-8-sig") for p in js_files]
css = [p.read_text(encoding="utf-8-sig") for p in css_files]
assert len(set(js)) == 1
assert len(set(css)) == 1

j, c = js[0], css[0]
for token in (
    "AURA_V123_SYSTEM_LIVE_COEXISTENCE_BEGIN",
    "const SYSTEM_LIVE_SELECTORS=[",
    "'.telemetry'",
    "'#auraSystemStatePanel:not([hidden])'",
    "function syncSystemLiveCoexistence(panel)",
    "getBoundingClientRect()",
    "--aura-v123-pr-right",
    "aura-v123-pr-system-live-coexist",
    "window.addEventListener('resize',syncSystemLiveSoon",
    "window.addEventListener('aura:workspace-changed',syncSystemLiveSoon)",
):
    assert token in j, token

assert "right:var(--aura-v123-pr-right,18px)" in c
assert "right:var(--aura-v123-pr-right,16px)" in c
assert "right:var(--aura-v123-pr-right,12px)" in c
assert "aura-v123-pr-system-live-coexist" in c

# Existing UX contracts retained.
assert "version: '1.2.3-ft5-ux1'" in j
assert "function senderValue(item)" in j
assert "width:clamp(430px,34vw,620px)" in c
assert "white-space:pre-line" in c

print("[PASS] v1.2.3 personal results / SYSTEM LIVE coexistence invariant")