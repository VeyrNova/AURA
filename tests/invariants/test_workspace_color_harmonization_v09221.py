from __future__ import annotations
import hashlib
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import AURA_VERSION

UI_RELEASE = "0.7.2.2-rc4.2"
UI_ROOT = (
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "AURA"
    / "ui"
    / ("v" + UI_RELEASE)
)

conv_css = [
    UI_ROOT / "src" / "aura-p0712-conversation-ui.css",
    UI_ROOT / "src" / "assets" / "aura-p0712-conversation-ui.css",
    UI_ROOT / "dist" / "assets" / "aura-p0712-conversation-ui.css",
]
rail_css = [
    UI_ROOT / "src" / "aura-p0702-left-rail.css",
    UI_ROOT / "src" / "assets" / "aura-p0702-left-rail.css",
    UI_ROOT / "dist" / "assets" / "aura-p0702-left-rail.css",
]
conv_js = [
    UI_ROOT / "src" / "aura-p0712-conversation-ui.js",
    UI_ROOT / "src" / "assets" / "aura-p0712-conversation-ui.js",
    UI_ROOT / "dist" / "assets" / "aura-p0712-conversation-ui.js",
]
rail_js = [
    UI_ROOT / "src" / "aura-p0702-left-rail.js",
    UI_ROOT / "src" / "assets" / "aura-p0702-left-rail.js",
    UI_ROOT / "dist" / "assets" / "aura-p0702-left-rail.js",
]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

assert AURA_VERSION == '0.9.4', AURA_VERSION
assert all(path.is_file() for path in conv_css + rail_css + conv_js + rail_js)

assert {sha(path) for path in conv_css} == {"6cf283b70e321feb274c8e8a3b5fff82409daecb2f8e4183fd040112d75d57fe"}
assert {sha(path) for path in rail_css} == {"2162fb9b4f39cd1b0113e2cd06d949fc19bff360251143ef438a37f3b44be4d5"}
assert {sha(path) for path in conv_js} == {"daf268c403fcae2264f0be77a18d3fa5009427422d7d16e3545bff1b0665ff31"}
assert {sha(path) for path in rail_js} == {"c9cc3a363344d7148cf2ad85deda5a9c779aca223f17d2c5f27cbfb7e5ba9b02"}

conv = conv_css[0].read_text(encoding="utf-8-sig", errors="replace")
rail = rail_css[0].read_text(encoding="utf-8-sig", errors="replace")
rail_j = rail_js[0].read_text(encoding="utf-8-sig", errors="replace")

assert conv.count("AURA V0.9.2.2.1 COLOR HARMONIZATION - CONVERSATION") == 1
assert rail.count("AURA V0.9.2.2.1 COLOR HARMONIZATION - SETTINGS") == 1

for token in [
    'body[data-aura-workspace="talk"] #conversation',
    ".aura-p0712-full-head",
    ".aura-p0712-full-title>span",
    ".aura-p0712-conversation-drawer",
    "#74dbe9",
    "rgba(111,228,247,.30)",
]:
    assert token in conv, token

for token in [
    ".aura-p0702-popover.aura-p0702-settings-popover",
    ".aura-p0702-settings-popover header",
    ".aura-p0702-settings-popover button:focus-visible",
    "#dffaff",
    "rgba(111,228,247,.32)",
]:
    assert token in rail, token

settings_block = rail.split(
    "AURA V0.9.2.2.1 COLOR HARMONIZATION - SETTINGS",
    1,
)[1]

assert ".aura-p0702-modules-popover" not in settings_block
assert ".aura-p0702-mail-popover" not in settings_block

assert 'data-module="mail"' in rail_j
assert 'data-module="agenda"' in rail_j
assert "aura-p0702-settings-popover" in rail_j

assert re.search(
    r"\[\s*['\"]calendar['\"]\s*,",
    rail_j,
    flags=re.I,
) is None

print("[PASS] AURA v0.9.2.2.1 Workspace Color Harmonization")
print("[PASS] Conversation = dark navy + cyan/blue primary")
print("[PASS] Settings = dark navy + cyan/blue primary")
print("[PASS] Modules/Mail CSS scope unchanged by Settings override")
print("[PASS] MAIL + AGENDA retained")
print("[PASS] no duplicate Calendar sidebar")
raise SystemExit(0)
