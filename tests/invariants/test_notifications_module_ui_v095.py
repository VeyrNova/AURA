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

rails = [
    UI_ROOT / "src" / "aura-p0702-left-rail.js",
    UI_ROOT / "src" / "assets" / "aura-p0702-left-rail.js",
    UI_ROOT / "dist" / "assets" / "aura-p0702-left-rail.js",
]

css = [
    UI_ROOT / "src" / "aura-p0702-left-rail.css",
    UI_ROOT / "src" / "assets" / "aura-p0702-left-rail.css",
    UI_ROOT / "dist" / "assets" / "aura-p0702-left-rail.css",
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def count_module(source, module_id):
    return len(
        re.findall(
            r'<button\b[^>]*\bdata-module=["\']'
            + re.escape(module_id)
            + r'["\'][^>]*>',
            source,
            flags=re.I,
        )
    )


assert AURA_VERSION == "0.9.5", AURA_VERSION
assert all(path.is_file() for path in rails)
assert all(path.is_file() for path in css)
assert {sha(path) for path in rails} == {"c9cc3a363344d7148cf2ad85deda5a9c779aca223f17d2c5f27cbfb7e5ba9b02"}
assert {sha(path) for path in css} == {"2162fb9b4f39cd1b0113e2cd06d949fc19bff360251143ef438a37f3b44be4d5"}

text = rails[0].read_text(
    encoding="utf-8-sig",
    errors="replace",
)

assert count_module(text, "mail") == 1
assert count_module(text, "agenda") == 1
assert count_module(text, "contacts") == 1
assert count_module(text, "documents") == 1
assert count_module(text, "system") == 0
assert count_module(text, "notifications") == 1

assert "AURA V0.9.5 D2 R3 NOTIFICATIONS ACTIVITY CENTER VISUAL ROUTING" in text
assert "<b>NOTIFICATIONS</b>" in text
assert "Centre d'activite et alertes" in text
assert "function openNotifications()" in text
assert "window.AuraEventWatchers" in text
assert "typeof ew.open==='function'" in text
assert "ew.open()" in text
assert "affiche mes notifications" in text
assert "event.stopPropagation()" in text

print("[PASS] AURA v0.9.5 NOTIFICATIONS Modules visual invariant")
print("[PASS] one NOTIFICATIONS card / no SYSTEM LIVE card")
print("[PASS] P0.8.1 Activity Center primary route")
print("[PASS] P0.8.3 presentation remains external to p0702")
