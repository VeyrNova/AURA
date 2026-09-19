from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from integrations.registry import IntegrationCapability
from security.permissions import Permission
from skills.developer_contract import SkillDeveloperContractError, build_skill_developer_contract_v102
from skills.lifecycle import SkillLifecycleManagerV102
from skills.manifest import SkillCapabilityRef, SkillManifest
from skills.registry import SkillCapabilityRegistryV100
from skills.runtime import SecureSkillRuntimeV101, SkillPermissionDeniedError, UnknownSkillRuntimeError


def _cap(cid, confirmation=False, risk="LOW", side="read_only"):
    return IntegrationCapability(
        capability_id=cid,
        action=cid.split(".", 1)[1],
        description="v1.0 final acceptance " + cid,
        risk_tier=risk,
        requires_confirmation=bool(confirmation),
        side_effect_class=side,
        evidence_required=True,
    )


class FakeRegistry:
    def __init__(self):
        self.capabilities = {
            ("browser.provider", "browser.search"): _cap("browser.search"),
            ("browser.provider", "browser.click"): _cap("browser.click", True, "MEDIUM", "state_change"),
        }
        self.calls = []

    def resolve_capability(self, provider_id, capability_id):
        return self.capabilities.get((provider_id, capability_id))

    def execute_integration(self, request, *, user_confirmed=False):
        self.calls.append((request, bool(user_confirmed)))
        status = "waiting_confirmation" if request.capability_id == "browser.click" and not user_confirmed else "success"
        return SimpleNamespace(
            request_id=request.request_id,
            provider_id=request.provider_id,
            capability_id=request.capability_id,
            status=status,
            ok=(status == "success"),
            receipt_id="final-" + request.request_id,
            output={"params": dict(request.params)},
            error=None,
            evidence_refs=(),
        )


ireg = FakeRegistry()
sreg = SkillCapabilityRegistryV100(integration_registry=ireg)
runtime = SecureSkillRuntimeV101(
    skill_registry=sreg,
    integration_registry=ireg,
    granted_permissions=(Permission.WEB_READ, Permission.BROWSER_MUTATE),
)
lifecycle = SkillLifecycleManagerV102(
    skill_registry=sreg,
    secure_runtime=runtime,
    aura_version="1.0.2",
)
manifest = SkillManifest(
    skill_id="final.acceptance",
    display_name="Final Acceptance Skill",
    skill_version="1.0.2",
    capabilities=(
        SkillCapabilityRef("browser.provider", "browser.search"),
        SkillCapabilityRef("browser.provider", "browser.click"),
    ),
)
contract = build_skill_developer_contract_v102(
    manifest=manifest,
    payload={
        "min_aura_version": "1.0.0",
        "max_aura_version": "1.0.9",
        "execution_model": "secure_runtime_v101",
        "install_scope": "metadata_only",
        "dynamic_code": False,
    },
)

# install: metadata only
assert lifecycle.install(contract).state == "installed"
assert sreg.get_manifest("final.acceptance") is None
assert not lifecycle.is_active("final.acceptance")
assert not ireg.calls

# inactive -> deny resolution
try:
    runtime.execute(skill_id="final.acceptance", provider_id="browser.provider", capability_id="browser.search")
    raise AssertionError("inactive skill executed")
except UnknownSkillRuntimeError:
    pass

# activate -> secure runtime -> integration registry
assert lifecycle.activate("final.acceptance").state == "active"
read = runtime.execute(
    skill_id="final.acceptance",
    provider_id="browser.provider",
    capability_id="browser.search",
    params={"query": "AURA final acceptance"},
    request_id="v1-final-read",
)
assert read.status == "success"
assert ireg.calls[-1][1] is False
assert ireg.calls[-1][0].origin == "skill.runtime.v101:final.acceptance"

# confirmation semantics preserved
pending = runtime.execute(
    skill_id="final.acceptance",
    provider_id="browser.provider",
    capability_id="browser.click",
    params={"selector": "#final"},
    request_id="v1-final-click-pending",
    user_confirmed=False,
)
assert pending.status == "waiting_confirmation"
assert ireg.calls[-1][1] is False
confirmed = runtime.execute(
    skill_id="final.acceptance",
    provider_id="browser.provider",
    capability_id="browser.click",
    params={"selector": "#final"},
    request_id="v1-final-click-confirmed",
    user_confirmed=True,
)
assert confirmed.status == "success"
assert ireg.calls[-1][1] is True

# missing permission fails before delegation
restricted = SecureSkillRuntimeV101(
    skill_registry=sreg,
    integration_registry=ireg,
    granted_permissions=(Permission.WEB_READ,),
)
before = len(ireg.calls)
try:
    restricted.execute(
        skill_id="final.acceptance",
        provider_id="browser.provider",
        capability_id="browser.click",
        params={"selector": "#blocked"},
    )
    raise AssertionError("missing permission allowed")
except SkillPermissionDeniedError:
    pass
assert len(ireg.calls) == before

# deactivate -> deny; uninstall -> provider catalog untouched
lifecycle.deactivate("final.acceptance")
try:
    runtime.execute(skill_id="final.acceptance", provider_id="browser.provider", capability_id="browser.search")
    raise AssertionError("deactivated skill executed")
except UnknownSkillRuntimeError:
    pass
lifecycle.activate("final.acceptance")
provider_snapshot = dict(ireg.capabilities)
assert lifecycle.uninstall("final.acceptance") is True
assert ireg.capabilities == provider_snapshot
assert sreg.get_manifest("final.acceptance") is None

# developer contract still forbids dynamic code
try:
    build_skill_developer_contract_v102(
        manifest=manifest,
        payload={"min_aura_version": "1.0.0", "dynamic_code": True},
    )
    raise AssertionError("dynamic code allowed")
except SkillDeveloperContractError:
    pass

print("[PASS] AURA Secure Skills Platform v1.0 final acceptance")
print("[PASS] install metadata-only; lifecycle gates runtime resolution")
print("[PASS] SecureSkillRuntimeV101 is the only execution path")
print("[PASS] permissions and confirmation semantics remain fail-closed")
print("[PASS] uninstall preserves canonical integration providers")
print("[PASS] dynamic Skill code remains forbidden")
