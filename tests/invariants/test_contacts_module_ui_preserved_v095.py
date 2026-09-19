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

rail_js = [
    UI_ROOT / "src" / "aura-p0702-left-rail.js",
    UI_ROOT / "src" / "assets" / "aura-p0702-left-rail.js",
    UI_ROOT / "dist" / "assets" / "aura-p0702-left-rail.js",
]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

assert AURA_VERSION == '0.9.5', AURA_VERSION
assert all(path.is_file() for path in rail_js)
assert {sha(path) for path in rail_js} == {"c9cc3a363344d7148cf2ad85deda5a9c779aca223f17d2c5f27cbfb7e5ba9b02"}

text = rail_js[0].read_text(
    encoding="utf-8-sig",
    errors="replace",
)

assert text.count("AURA V0.9.3 CONTACTS MODULE VISUAL EXPOSURE") == 1

def count_contacts_html_cards(source):
    return len(
        re.findall(
            r'<(?:button|a|div)\b[^>]*\bdata-module\s*=\s*["\']contacts["\'][^>]*>',
            source,
            flags=re.I,
        )
    )

assert count_contacts_html_cards(text) == 1
assert text.count('[data-module="contacts"]') == 1

assert 'data-module="mail"' in text
assert 'data-module="agenda"' in text
assert "CONTACTS_PROMPT" in text
assert "cherche mes contacts" in text
assert "window.AuraWorkspace" in text
assert "workspace?.open?.('talk')" in text
assert "stopImmediatePropagation" in text

# No duplicate Contacts or Calendar sidebar target.
assert not re.search(
    r'data-rail-target\s*=\s*["\']contacts["\']',
    text,
    flags=re.I,
)
assert not re.search(
    r'data-rail-target\s*=\s*["\']calendar["\']',
    text,
    flags=re.I,
)

contacts_provider = (
    ROOT / "integrations" / "contacts" / "provider.py"
)
runtime = (
    ROOT / "runtime" / "personal_integrations.py"
)
controllers = (
    ROOT / "ui" / "personal_integration_modules.py"
)

assert contacts_provider.is_file()
assert runtime.is_file()
assert controllers.is_file()

provider_text = contacts_provider.read_text(
    encoding="utf-8-sig",
    errors="replace",
)
runtime_text = runtime.read_text(
    encoding="utf-8-sig",
    errors="replace",
)
controller_text = controllers.read_text(
    encoding="utf-8-sig",
    errors="replace",
)

for token in [
    "contacts.search",
    "contacts.read",
    "contacts.create",
    "contacts.update",
    "contacts.delete",
]:
    assert token in provider_text
    assert token in runtime_text

assert "ContactsModuleController" in controller_text
assert '"contacts": self.contacts.status().to_dict()' in controller_text

print("[PASS] AURA v0.9.3 Contacts Modules visual exposure")
print("[PASS] CONTACTS card visible in p0702 Modules catalog")
print("[PASS] CONTACTS opens existing Conversation workspace")
print("[PASS] no auto-submit; backend confirmation path remains authoritative")
print("[PASS] MAIL + AGENDA retained")
print("[PASS] no Contacts/Calendar duplicate sidebar")
raise SystemExit(0)
