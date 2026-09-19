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

assert AURA_VERSION == '0.9.4', AURA_VERSION

UI_ROOT = (
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "AURA"
    / "ui"
    / "v0.7.2.2-rc4.2"
)

js_paths = [
    UI_ROOT / "src" / "aura-p0702-left-rail.js",
    UI_ROOT / "src" / "assets" / "aura-p0702-left-rail.js",
    UI_ROOT / "dist" / "assets" / "aura-p0702-left-rail.js",
]

css_paths = [
    UI_ROOT / "src" / "aura-p0702-left-rail.css",
    UI_ROOT / "src" / "assets" / "aura-p0702-left-rail.css",
    UI_ROOT / "dist" / "assets" / "aura-p0702-left-rail.css",
]

for path in js_paths + css_paths:
    assert path.is_file(), path

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

assert len({sha(path) for path in js_paths}) == 1
assert len({sha(path) for path in css_paths}) == 1

js = js_paths[0].read_text(
    encoding="utf-8-sig",
    errors="replace",
)
css = css_paths[0].read_text(
    encoding="utf-8-sig",
    errors="replace",
)

assert "AURA_V0922_MODULES_AGENDA_UI_BEGIN" in js
assert 'data-module="mail"' in js
assert 'data-module="agenda"' in js
assert "function openMailModule()" in js
assert "function ensureAgendaCalendarBridge()" in js
assert "id==='mail')openMailModule()" in js
assert "id==='agenda')openPlan('agenda')" in js
assert "data-aura-calendar-bridge" in js
assert "quels sont mes prochains rendez-vous" in js
assert "suis-je libre demain entre 14h et 16h" in js
assert "affiche mes mails" in js
assert "prepare un brouillon de mail a " in js
assert "envoie un mail a " in js

# Existing sidebar ownership remains Agenda + Tasks.
assert re.search(
    r"\[\s*['\"]tasks['\"]\s*,\s*['\"]T",
    js,
    flags=re.I,
)
assert re.search(
    r"\[\s*['\"]agenda['\"]\s*,\s*['\"]AGENDA['\"]",
    js,
    flags=re.I,
)
assert not re.search(
    r"\[\s*['\"]calendar['\"]\s*,",
    js,
    flags=re.I,
)

# Agenda still routes through the historical plan/reminders surface,
# enriched with Calendar quick access.
assert "openPlan('agenda')" in js
assert 'data-tab="reminders"' in js
assert "planSubmode==='agenda'" in js

assert "AURA_V0922_MODULES_COLOR_FIX_BEGIN" in css
for token in (
    ".aura-p0702-modules-popover",
    ".aura-p0702-mail-popover",
    ".aura-v0922-agenda-calendar-bridge",
    "rgba(111,228,247,.38)",
    "#74dbe9",
    "#79e0ec",
):
    assert token in css, token

# Provider/controller authority remains existing project code.
final_modules = (ROOT / "ui" / "final_modules.py").read_text(
    encoding="utf-8-sig",
    errors="replace",
)
controllers = (ROOT / "ui" / "personal_integration_modules.py").read_text(
    encoding="utf-8-sig",
    errors="replace",
)
assert "class AgendaPage" in final_modules
assert "class MailPage" in final_modules
assert "class CalendarModuleController" in controllers
assert "class MailModuleController" in controllers

print("[PASS] v0.9.2.2 D2 Modules + Agenda UI invariant")
raise SystemExit(0)
