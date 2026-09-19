from __future__ import annotations
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import AURA_VERSION

assert AURA_VERSION == '0.9.4', AURA_VERSION

core = (ROOT / "core" / "aura_core.py").read_text(encoding="utf-8-sig")
main = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8-sig")
mods = (ROOT / "ui" / "final_modules.py").read_text(encoding="utf-8-sig")
controllers = (ROOT / "ui" / "personal_integration_modules.py").read_text(
    encoding="utf-8-sig"
)

assert "AURA_V0921_RUNTIME_WIRING_BEGIN" in core
assert "AURA_V0921_RUNTIME_WIRING_END" in core
assert "PersonalIntegrationDispatcher" in core
assert "build_synthetic_runtime_context" in core

assert "class MailPage" in mods
assert "class AgendaPage" in mods
assert "MODE SYNTHETIQUE" in mods
assert "REPONDRE AU MAIL SELECTIONNE" in mods
assert "CALENDAR / AGENDA" in mods
assert "DECALER +30 MIN" in mods

assert "MailPage" in main
assert "AURA_V0921_UI_BIND_BEGIN" in main
assert "AURA_V0921_UI_BIND_END" in main
assert "PersonalIntegrationModules" in main
assert "set_controller" in main

for capability in (
    "email.search",
    "email.read",
    "email.list_attachments",
    "email.create_draft",
    "email.send",
    "email.reply",
    "email.forward",
    "email.archive",
    "email.trash",
    "email.label",
    "calendar.list",
    "calendar.search_events",
    "calendar.read_event",
    "calendar.free_busy",
    "calendar.create_event",
    "calendar.update_event",
    "calendar.delete_event",
    "calendar.respond_invitation",
):
    assert capability in controllers, capability

ast.parse(core)
ast.parse(main)
ast.parse(mods)
ast.parse(controllers)

print("[PASS] v0.9.2.1 visible Mail/Calendar runtime wiring invariant")
raise SystemExit(0)
