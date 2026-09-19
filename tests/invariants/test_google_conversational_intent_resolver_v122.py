from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.personal_integrations import (
    CALENDAR_PROVIDER_ID,
    CONTACTS_PROVIDER_ID,
    EMAIL_PROVIDER_ID,
    FILES_PROVIDER_ID,
    IntegrationIntentResolver,
)

resolver = IntegrationIntentResolver(timezone_name="Europe/Paris")


def check(text, provider, capability):
    intent = resolver.resolve_integration_intent(text)
    assert intent is not None, (text, "intent=None")
    assert intent.provider_id == provider, (text, intent.provider_id, provider)
    assert intent.capability_id == capability, (text, intent.capability_id, capability)
    return intent


# Gmail natural conversation: list/plural requests must be email.search, not Gemini.
for phrase in (
    "Aura, affiche mes derniers mails",
    "Aura, montre mes derniers emails",
    "liste mes mails",
    "mes derniers courriels",
):
    intent = check(phrase, EMAIL_PROVIDER_ID, "email.search")
    query = dict(intent.params).get("query") or {}
    assert query.get("text") == "", (phrase, query)
    assert int(query.get("limit") or 0) == 10, (phrase, query)

# Singular explicit mail read remains the historical email.read behavior.
intent = check("Aura, affiche le mail msg-001", EMAIL_PROVIDER_ID, "email.read")
assert dict(intent.params).get("message_id") == "msg-001"

# Calendar existing coverage must remain intact.
check("Aura, affiche mon agenda", CALENDAR_PROVIDER_ID, "calendar.search_events")
check(
    "Aura, quels sont mes prochains rendez-vous",
    CALENDAR_PROVIDER_ID,
    "calendar.search_events",
)

# Contacts existing coverage must remain intact.
check("Aura, affiche mes contacts", CONTACTS_PROVIDER_ID, "contacts.search")
check("Aura, cherche le contact Martin", CONTACTS_PROVIDER_ID, "contacts.search")

# Drive conversational aliases now map into the already-certified Files provider.
check("Aura, affiche mes fichiers Drive", FILES_PROVIDER_ID, "files.list")
drive = check(
    "Aura, cherche Budget dans mon Google Drive",
    FILES_PROVIDER_ID,
    "files.search",
)
drive_query = str((dict(drive.params).get("query") or {}).get("text") or "").strip()
assert drive_query.lower() == "budget", drive_query

# Ordinary chat remains LLM eligible.
for phrase in (
    "Explique-moi les trous noirs",
    "Quelle météo demain ?",
    "Écris un poème",
):
    assert resolver.resolve_integration_intent(phrase) is None, phrase

source = (ROOT / "runtime" / "personal_integrations.py").read_text(
    encoding="utf-8-sig",
    errors="replace",
)
assert "AURA_V122_GOOGLE_CONVERSATIONAL_COVERAGE_BEGIN" in source
assert "AURA_V122_GOOGLE_CONVERSATIONAL_COVERAGE_END" in source

# No replacement UI router may return: AuraCore/MainWindow keep their certified path.
main_source = (ROOT / "ui" / "main_window.py").read_text(
    encoding="utf-8-sig",
    errors="replace",
)
assert "AURA v1.2.2 PERSONAL_INTEGRATION_PRE_LLM" not in main_source
assert "dispatch_personal_before_llm_v122" not in main_source

print("[PASS] Gmail natural plural/list conversation -> email.search")
print("[PASS] explicit singular mail read preserved")
print("[PASS] Calendar / Contacts existing resolver coverage preserved")
print("[PASS] Google Drive aliases -> certified Files provider")
print("[PASS] ordinary chat remains LLM eligible")
print("[PASS] no pre-LLM MainWindow router reintroduced")
