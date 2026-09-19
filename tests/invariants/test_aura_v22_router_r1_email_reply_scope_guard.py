from __future__ import annotations

from pathlib import Path
import hashlib
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TARGET = ROOT / "runtime" / "personal_integrations.py"
text = TARGET.read_text(encoding="utf-8-sig")

assert "AURA_V22_ROUTER_R1_EMAIL_REPLY_SCOPE_GUARD" in text
assert 'if re.search(r"\\b(reponds|repondre|reply)\\b", normalized):' not in text

from runtime.personal_integrations import IntegrationIntentResolver

resolver = IntegrationIntentResolver.__new__(IntegrationIntentResolver)

def resolve(text: str):
    return resolver.resolve_integration_intent(text)

# Exact regression from the AEC forensic.
assert resolve(
    "Réponds uniquement par cette phrase : mesure résiduelle AEC vingt-trois, "
    "un deux trois quatre cinq six sept huit neuf dix."
) is None

# Other ordinary conversation prompts containing "réponds" must remain conversation.
assert resolve("Réponds simplement oui.") is None
assert resolve("Réponds en français.") is None
assert resolve("Réponds uniquement par bonjour.") is None
assert resolve("Peux-tu répondre brièvement à cette question ?") is None

# Explicit Gmail reply intents must remain supported.
r = resolve("Réponds au mail msg-001")
assert r is not None and r.capability_id == "email.reply"
r = resolve("Réponds à msg-001")
assert r is not None and r.capability_id == "email.reply"

# Existing Gmail search/list controls remain intact.
r = resolve("cherche mes mails")
assert r is not None and r.capability_id == "email.search"
r = resolve("affiche mes mails")
assert r is not None and r.capability_id == "email.search"

print("[PASS] exact AEC phrase stays out of Gmail")
print("[PASS] neutral 'reponds' conversation prompts stay out of Gmail")
print("[PASS] explicit email.reply with mail context remains supported")
print("[PASS] explicit email.reply with message id remains supported")
print("[PASS] Gmail search/list controls remain supported")
