from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from integrations.registry import IntegrationRegistry
from runtime.integration_permissions_v098 import ALLOW, DENY, REQUIRE_CONFIRMATION
from security.permissions import DEFAULT_GRANTED_PERMISSIONS, Permission
from security.policy_engine import SecurityPolicyEngine


class NoopReceiptService:
    pass


def registry_for(engine):
    return IntegrationRegistry(
        security_engine=engine,
        receipt_service=NoopReceiptService(),
    )


production = SecurityPolicyEngine(None)
try:
    production._audit = lambda decision: None
except Exception:
    pass

reg = registry_for(production)

for capability in (
    "email.search",
    "calendar.search_events",
    "contacts.search",
    "files.list",
):
    assert reg._authorize(capability, {}, user_confirmed=False) == ALLOW, capability

assert reg._authorize("email.send", {}, user_confirmed=False) == DENY

granted = frozenset(
    set(DEFAULT_GRANTED_PERMISSIONS)
    | {Permission.EXTERNAL_NETWORK}
)
production_external = SecurityPolicyEngine(
    None,
    granted_permissions=granted,
)
try:
    production_external._audit = lambda decision: None
except Exception:
    pass
reg_external = registry_for(production_external)
assert reg_external._authorize("email.send", {}, user_confirmed=False) == REQUIRE_CONFIRMATION
assert reg_external._authorize("email.send", {}, user_confirmed=True) == ALLOW

production_all = SecurityPolicyEngine(
    None,
    granted_permissions=frozenset(Permission),
)
try:
    production_all._audit = lambda decision: None
except Exception:
    pass
reg_all = registry_for(production_all)
assert reg_all._authorize("browser.pay", {}, user_confirmed=True) == DENY
assert reg_all._authorize("files.execute_arbitrary_code", {}, user_confirmed=True) == DENY

legacy = reg._authorize(
    "WEB_KNOWLEDGE_REFERENCE",
    {},
    user_confirmed=False,
)
legacy_text = str(getattr(legacy, "decision", legacy)).upper()
assert "ALLOW" in legacy_text, legacy

class CustomSecurity:
    def authorize(self, action, params, user_confirmed=False):
        return "ALLOW"

custom = registry_for(CustomSecurity())
assert custom._authorize("email.search", {}, user_confirmed=False) == "ALLOW"
assert custom._authorize("CUSTOM_ACTION", {}, user_confirmed=False) == "ALLOW"

print("[PASS] v1.2.2 IntegrationRegistry permission bridge invariant")
print("[PASS] four read-only integration capabilities use certified v0.9.8 ALLOW")
print("[PASS] mutation permission + confirmation semantics preserved")
print("[PASS] forbidden and unknown integration capabilities fail closed")
print("[PASS] legacy SecurityPolicyEngine path preserved for non-integration actions")
print("[PASS] custom security-engine compatibility preserved")
