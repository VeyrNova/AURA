from __future__ import annotations

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

assert AURA_VERSION == '0.9.5'
assert all(path.is_file() for path in rails)
assert len({path.read_bytes() for path in rails}) == 1

text = rails[0].read_text(
    encoding="utf-8-sig",
    errors="replace",
)

def count_cards(source, module_id):
    return len(
        re.findall(
            r"<button\b[^>]*\bdata-module=['\"]"
            + re.escape(module_id)
            + r"['\"][^>]*>",
            source,
            flags=re.I,
        )
    )

assert count_cards(text, "system") == 0

for module_id in [
    "mail",
    "agenda",
    "contacts",
    "documents",
]:
    assert count_cards(
        text,
        module_id,
    ) == 1

assert "DIAGNOSTICS" in text.upper()

print("[PASS] AURA v0.9.4 Modules SYSTEM LIVE de-dup")
print("[PASS] permanent right SYSTEM LIVE remains external to Modules")
print("[PASS] DIAGNOSTICS remains detailed system workspace")
