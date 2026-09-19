from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from integrations.calendar.provider import CONFIRMATION_CAPABILITIES as CALENDAR_CONFIRMATION
from integrations.contacts.provider import CONFIRMATION_CAPABILITIES as CONTACTS_CONFIRMATION
from integrations.email.provider import CONFIRMATION_CAPABILITIES as EMAIL_CONFIRMATION
from integrations.files.provider import CONFIRMATION_CAPABILITIES as FILES_CONFIRMATION
from runtime.productivity_mission_bridge_v097 import _CERTIFIED_BROWSER_CAPABILITIES
from runtime.integration_permissions_v098 import (
    ALLOW,
    DENY,
    REQUIRE_CONFIRMATION,
    CANONICAL_PROVIDER_CAPABILITIES_V098,
    DENIED_BROWSER_CAPABILITIES_V098,
    INTEGRATION_PERMISSION_RULES_V098,
    action_policy_for_integration_capability_v098,
    evaluate_integration_permission_v098,
    validate_integration_permission_contract_v098,
)
from security.permissions import DEFAULT_GRANTED_PERMISSIONS, Permission


assert validate_integration_permission_contract_v098() == ()
assert len(INTEGRATION_PERMISSION_RULES_V098) == 53

assert set(CANONICAL_PROVIDER_CAPABILITIES_V098) == {
    "browser.provider",
    "calendar.provider",
    "contacts.provider",
    "email.provider",
    "files.provider",
    "notifications.provider",
}
assert sum(len(v) for v in CANONICAL_PROVIDER_CAPABILITIES_V098.values()) == 53

# Provider IDs and non-capability artifact strings from the FT1 lexical scan are excluded.
for excluded in (
    "browser.provider",
    "calendar.provider",
    "contacts.provider",
    "email.provider",
    "files.provider",
    "notifications.provider",
    "aura.txt",
    "welcome.txt",
    "aura.notification-action-receipt.v1",
):
    assert excluded not in INTEGRATION_PERMISSION_RULES_V098

allowed_browser = {
    cap
    for cap, rule in INTEGRATION_PERMISSION_RULES_V098.items()
    if rule.provider_id == "browser.provider" and rule.allowed
}
assert allowed_browser == set(_CERTIFIED_BROWSER_CAPABILITIES)
assert DENIED_BROWSER_CAPABILITIES_V098 == {
    "browser.antibot_bypass",
    "browser.captcha_bypass",
    "browser.credentials",
    "browser.pay",
    "browser.purchase",
    "browser.transfer",
}
for cap in DENIED_BROWSER_CAPABILITIES_V098:
    decision = evaluate_integration_permission_v098(
        cap,
        granted_permissions=frozenset(Permission),
        user_confirmed=True,
    )
    assert decision.decision == DENY
    assert decision.reason == "capability_explicitly_denied"

# Existing provider confirmation contracts are mirrored, not weakened.
browser_confirm = {
    cap
    for cap in allowed_browser
    if INTEGRATION_PERMISSION_RULES_V098[cap].confirmation_required
}
assert browser_confirm == {
    "browser.click",
    "browser.fill",
    "browser.submit",
    "browser.download",
}

calendar_confirm = {
    cap
    for cap in CANONICAL_PROVIDER_CAPABILITIES_V098["calendar.provider"]
    if INTEGRATION_PERMISSION_RULES_V098[cap].confirmation_required
}
contacts_confirm = {
    cap
    for cap in CANONICAL_PROVIDER_CAPABILITIES_V098["contacts.provider"]
    if INTEGRATION_PERMISSION_RULES_V098[cap].confirmation_required
}
email_confirm = {
    cap
    for cap in CANONICAL_PROVIDER_CAPABILITIES_V098["email.provider"]
    if INTEGRATION_PERMISSION_RULES_V098[cap].confirmation_required
}
files_confirm = {
    cap
    for cap in CANONICAL_PROVIDER_CAPABILITIES_V098["files.provider"]
    if INTEGRATION_PERMISSION_RULES_V098[cap].confirmation_required
}

assert calendar_confirm == set(CALENDAR_CONFIRMATION)
assert contacts_confirm == set(CONTACTS_CONFIRMATION)
assert email_confirm == set(EMAIL_CONFIRMATION)
assert files_confirm == set(FILES_CONFIRMATION)
assert INTEGRATION_PERMISSION_RULES_V098["notifications.clear"].confirmation_required is True
for cap in (
    "notifications.create",
    "notifications.mark_read",
    "notifications.dismiss",
):
    assert INTEGRATION_PERMISSION_RULES_V098[cap].confirmation_required is False

# Security permissions are existing enum members and ActionPolicy is reused.
for cap, rule in INTEGRATION_PERMISSION_RULES_V098.items():
    assert isinstance(rule.permission, Permission)
    policy = action_policy_for_integration_capability_v098(cap)
    if rule.allowed:
        assert policy is not None
        assert policy.permission is rule.permission
        assert policy.risk is rule.risk
        assert policy.confirmation_required is rule.confirmation_required
    else:
        assert policy is None

# Fail closed on unknown capabilities.
unknown = evaluate_integration_permission_v098(
    "email.execute_arbitrary_code",
    granted_permissions=frozenset(Permission),
    user_confirmed=True,
)
assert unknown.decision == DENY
assert unknown.reason == "unknown_integration_capability"

# A read-only default-granted capability can be allowed.
read_decision = evaluate_integration_permission_v098("files.read")
assert Permission.AUTHORIZED_FILE_READ in DEFAULT_GRANTED_PERMISSIONS
assert read_decision.decision == ALLOW

# Sensitive permissions that are not granted are denied before confirmation.
send_default = evaluate_integration_permission_v098("email.send", user_confirmed=True)
assert Permission.EXTERNAL_NETWORK not in DEFAULT_GRANTED_PERMISSIONS
assert send_default.decision == DENY
assert send_default.reason == "permission_not_granted"

# When permission is explicitly granted, confirmation is still mandatory.
grants = frozenset(set(DEFAULT_GRANTED_PERMISSIONS) | {Permission.EXTERNAL_NETWORK})
send_wait = evaluate_integration_permission_v098(
    "email.send",
    granted_permissions=grants,
    user_confirmed=False,
)
assert send_wait.decision == REQUIRE_CONFIRMATION
send_ok = evaluate_integration_permission_v098(
    "email.send",
    granted_permissions=grants,
    user_confirmed=True,
)
assert send_ok.decision == ALLOW

# Browser mutation permissions remain non-default.
assert Permission.BROWSER_MUTATE not in DEFAULT_GRANTED_PERMISSIONS
browser_grants = frozenset(set(DEFAULT_GRANTED_PERMISSIONS) | {Permission.BROWSER_MUTATE})
click_wait = evaluate_integration_permission_v098(
    "browser.click",
    granted_permissions=browser_grants,
    user_confirmed=False,
)
assert click_wait.decision == REQUIRE_CONFIRMATION
click_ok = evaluate_integration_permission_v098(
    "browser.click",
    granted_permissions=browser_grants,
    user_confirmed=True,
)
assert click_ok.decision == ALLOW

print("[PASS] Integration permissions contract v0.9.8")
print("[PASS] 53 canonical capabilities mapped across 6 providers")
print("[PASS] lexical provider IDs/artifact strings excluded")
print("[PASS] existing Permission/RiskLevel/ActionPolicy authorities reused")
print("[PASS] provider confirmation contracts preserved")
print("[PASS] sensitive permissions fail closed when not granted")
print("[PASS] explicit confirmation remains required after permission grant")
print("[PASS] six forbidden browser capabilities remain explicitly denied")
print("[PASS] unknown integration capabilities fail closed")
