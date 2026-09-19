from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from integrations.registry import (
    IntegrationCapability,
)
from runtime.integration_permissions_v098 import (
    ALLOW,
    DENY,
    REQUIRE_CONFIRMATION,
    validate_integration_permission_contract_v098,
)
from security.permissions import Permission
from skills.manifest import SkillCapabilityRef, SkillManifest
from skills.registry import SkillCapabilityRegistryV100
from skills.runtime import (
    SecureSkillRuntimeV101,
    SkillPermissionDeniedError,
    SkillRuntimeContractError,
    UnknownSkillBindingError,
    UnknownSkillRuntimeError,
)


def cap(capability_id, *, confirmation=False, risk="LOW", side="read_only"):
    return IntegrationCapability(
        capability_id=capability_id,
        action=capability_id.split(".", 1)[1],
        description="v1.0.1 secure runtime acceptance " + capability_id,
        risk_tier=risk,
        requires_confirmation=bool(confirmation),
        side_effect_class=side,
        evidence_required=True,
    )


class FakeIntegrationRegistry:
    def __init__(self):
        self.capabilities = {
            ("browser.provider", "browser.search"): cap("browser.search"),
            ("browser.provider", "browser.click"): cap(
                "browser.click",
                confirmation=True,
                risk="MEDIUM",
                side="state_change",
            ),
        }
        self.calls = []

    def resolve_capability(self, provider_id, capability_id):
        return self.capabilities.get((provider_id, capability_id))

    def execute_integration(self, request, *, user_confirmed=False):
        self.calls.append(
            {
                "request": request,
                "user_confirmed": bool(user_confirmed),
            }
        )
        status = (
            "waiting_confirmation"
            if request.capability_id == "browser.click"
            and not user_confirmed
            else "success"
        )
        return SimpleNamespace(
            request_id=request.request_id,
            provider_id=request.provider_id,
            capability_id=request.capability_id,
            status=status,
            ok=(status == "success"),
            receipt_id="receipt-" + request.request_id,
            output={"echo": dict(request.params)},
            error=None,
            evidence_refs=(),
        )


assert validate_integration_permission_contract_v098() == ()

fake = FakeIntegrationRegistry()
skill_registry = SkillCapabilityRegistryV100(
    integration_registry=fake,
)

manifest = SkillManifest(
    skill_id="browser.safe",
    display_name="Browser Safe",
    skill_version="1.0.1",
    capabilities=(
        SkillCapabilityRef(
            "browser.provider",
            "browser.search",
        ),
        SkillCapabilityRef(
            "browser.provider",
            "browser.click",
        ),
    ),
)
skill_registry.register_manifest(manifest)

runtime = SecureSkillRuntimeV101(
    skill_registry=skill_registry,
    integration_registry=fake,
    granted_permissions=(
        Permission.WEB_READ,
        Permission.BROWSER_MUTATE,
    ),
)

# Read-only capability: preflight ALLOW and exactly one delegation.
pre = runtime.preflight(
    skill_id="browser.safe",
    provider_id="browser.provider",
    capability_id="browser.search",
)
assert pre.decision == ALLOW
assert pre.requires_confirmation is False
assert len(fake.calls) == 0

result = runtime.execute(
    skill_id="browser.safe",
    provider_id="browser.provider",
    capability_id="browser.search",
    params={"query": "AURA"},
    request_id="v101-search",
)
assert result.status == "success"
assert len(fake.calls) == 1
call = fake.calls[-1]
assert call["user_confirmed"] is False
assert call["request"].origin == "skill.runtime.v101:browser.safe"
assert call["request"].capability_id == "browser.search"
assert dict(call["request"].params) == {"query": "AURA"}

# State-changing capability: preflight requires explicit confirmation.
pre_click = runtime.preflight(
    skill_id="browser.safe",
    provider_id="browser.provider",
    capability_id="browser.click",
    user_confirmed=False,
)
assert pre_click.decision == REQUIRE_CONFIRMATION
before = len(fake.calls)

waiting = runtime.execute(
    skill_id="browser.safe",
    provider_id="browser.provider",
    capability_id="browser.click",
    params={"selector": "#safe"},
    request_id="v101-click-pending",
    user_confirmed=False,
)
assert waiting.status == "waiting_confirmation"
assert len(fake.calls) == before + 1
assert fake.calls[-1]["user_confirmed"] is False

confirmed = runtime.execute(
    skill_id="browser.safe",
    provider_id="browser.provider",
    capability_id="browser.click",
    params={"selector": "#safe"},
    request_id="v101-click-confirmed",
    user_confirmed=True,
)
assert confirmed.status == "success"
assert fake.calls[-1]["user_confirmed"] is True

# Missing permission is fail-closed and never reaches IntegrationRegistry.
restricted = SecureSkillRuntimeV101(
    skill_registry=skill_registry,
    integration_registry=fake,
    granted_permissions=(Permission.WEB_READ,),
)
before = len(fake.calls)
deny_pre = restricted.preflight(
    skill_id="browser.safe",
    provider_id="browser.provider",
    capability_id="browser.click",
)
assert deny_pre.decision == DENY
try:
    restricted.execute(
        skill_id="browser.safe",
        provider_id="browser.provider",
        capability_id="browser.click",
        params={"selector": "#blocked"},
    )
    raise AssertionError("missing permission must fail")
except SkillPermissionDeniedError:
    pass
assert len(fake.calls) == before

# Unknown skill and unbound capability fail before delegation.
before = len(fake.calls)
try:
    runtime.execute(
        skill_id="missing.skill",
        provider_id="browser.provider",
        capability_id="browser.search",
    )
    raise AssertionError("unknown skill must fail")
except UnknownSkillRuntimeError:
    pass

try:
    runtime.execute(
        skill_id="browser.safe",
        provider_id="browser.provider",
        capability_id="browser.read",
    )
    raise AssertionError("unbound capability must fail")
except UnknownSkillBindingError:
    pass
assert len(fake.calls) == before

# Reserved confirmation spoofing is blocked before permission/delegation.
before = len(fake.calls)
try:
    runtime.execute(
        skill_id="browser.safe",
        provider_id="browser.provider",
        capability_id="browser.click",
        params={
            "selector": "#spoof",
            "user_confirmed": True,
        },
        user_confirmed=False,
    )
    raise AssertionError("confirmation spoof param must fail")
except SkillRuntimeContractError:
    pass
assert len(fake.calls) == before

# Runtime must expose only the narrow preflight/execute boundary.
public = {
    name
    for name, member in inspect.getmembers(
        SecureSkillRuntimeV101,
        predicate=inspect.isfunction,
    )
    if not name.startswith("_")
}
assert public == {"preflight", "execute"}

# Static source guard: no alternate execution/network/dynamic-code stack.
source_path = ROOT / "skills" / "runtime.py"
source = source_path.read_text(
    encoding="utf-8-sig",
)
tree = ast.parse(source, filename=str(source_path))

forbidden_import_roots = {
    "subprocess",
    "socket",
    "requests",
    "httpx",
    "urllib",
    "runpy",
    "importlib",
}
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for item in node.names:
            assert item.name.split(".", 1)[0] not in forbidden_import_roots
    elif isinstance(node, ast.ImportFrom):
        if node.module:
            assert node.module.split(".", 1)[0] not in forbidden_import_roots
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            assert node.func.id not in {
                "eval",
                "exec",
                "compile",
                "__import__",
            }

assert "ActionReceiptService" not in source
assert "SecurityPolicyEngine(" not in source
assert "execute_integration(" in source
assert "user_confirmed=bool(user_confirmed)" in source

print("[PASS] Secure Skill Runtime v1.0.1")
print("[PASS] only registered v1.0.0 Skill bindings can execute")
print("[PASS] v0.9.8 permission decisions fail closed before delegation")
print("[PASS] confirmation-required actions preserve the existing confirmation path")
print("[PASS] runtime never forces user_confirmed=True")
print("[PASS] reserved confirmation spoofing is rejected")
print("[PASS] actual execution delegates only to IntegrationRegistry.execute_integration")
print("[PASS] no direct Python/subprocess/network/receipt/security authority is duplicated")
