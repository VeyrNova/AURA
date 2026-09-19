from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from integrations.registry import IntegrationCapability
from runtime.integration_permissions_v098 import (
    get_integration_permission_rule_v098,
    validate_integration_permission_contract_v098,
)
from security.permissions import Permission
from skills.manifest import (
    SkillCapabilityRef,
    SkillManifest,
    SkillManifestError,
)
from skills.registry import (
    DeniedSkillCapabilityError,
    DuplicateSkillError,
    SkillCapabilityRegistryV100,
    UnknownSkillCapabilityError,
)


def cap(capability_id, *, confirmation=False, risk="LOW", side="read_only"):
    return IntegrationCapability(
        capability_id=capability_id,
        action=capability_id.split(".", 1)[1],
        description="v1.0.0 acceptance " + capability_id,
        risk_tier=risk,
        requires_confirmation=bool(confirmation),
        side_effect_class=side,
        evidence_required=True,
    )


class FakeIntegrationRegistry:
    def __init__(self):
        self.capabilities = {
            ("email.provider", "email.search"): cap("email.search"),
            ("email.provider", "email.send"): cap(
                "email.send",
                confirmation=True,
                risk="HIGH",
                side="external_side_effect",
            ),
            ("calendar.provider", "calendar.list"): cap("calendar.list"),
            ("files.provider", "files.read"): cap("files.read"),
            ("browser.provider", "browser.search"): cap("browser.search"),
            ("browser.provider", "browser.captcha_bypass"): cap(
                "browser.captcha_bypass",
                risk="CRITICAL",
                side="denied",
            ),
        }

    def resolve_capability(self, provider_id, capability_id):
        return self.capabilities.get((provider_id, capability_id))


assert validate_integration_permission_contract_v098() == ()

# Manifest validation.
manifest = SkillManifest(
    skill_id="personal.research",
    display_name="Personal Research",
    skill_version="1.0.0",
    description="Read-only multi-provider skill",
    capabilities=(
        SkillCapabilityRef("email.provider", "email.search"),
        SkillCapabilityRef("calendar.provider", "calendar.list"),
        SkillCapabilityRef("files.provider", "files.read"),
        SkillCapabilityRef("browser.provider", "browser.search"),
    ),
    metadata={"owner": "AURA", "secure": True},
)
assert manifest.skill_id == "personal.research"
assert manifest.skill_version == "1.0.0"
assert len(manifest.capabilities) == 4

try:
    manifest.metadata["x"] = 1
    raise AssertionError("metadata must be immutable")
except TypeError:
    pass

for bad in (
    lambda: SkillCapabilityRef("email.provider", "files.read"),
    lambda: SkillManifest(
        skill_id="Bad Skill",
        display_name="Bad",
        skill_version="1.0.0",
        capabilities=(SkillCapabilityRef("email.provider", "email.search"),),
    ),
    lambda: SkillManifest(
        skill_id="bad.version",
        display_name="Bad",
        skill_version="one",
        capabilities=(SkillCapabilityRef("email.provider", "email.search"),),
    ),
    lambda: SkillManifest(
        skill_id="duplicate.refs",
        display_name="Bad",
        skill_version="1.0.0",
        capabilities=(
            SkillCapabilityRef("email.provider", "email.search"),
            SkillCapabilityRef("email.provider", "email.search"),
        ),
    ),
):
    try:
        bad()
        raise AssertionError("invalid manifest/ref must fail closed")
    except SkillManifestError:
        pass

# Registry references existing IntegrationCapability and Permission authorities.
fake = FakeIntegrationRegistry()
registry = SkillCapabilityRegistryV100(integration_registry=fake)
registry.register_manifest(manifest)

assert registry.get_manifest("personal.research") is manifest
assert registry.list_manifests() == (manifest,)
bindings = registry.list_bindings("personal.research")
assert len(bindings) == 4
assert all(isinstance(x.integration_capability, IntegrationCapability) for x in bindings)
assert all(isinstance(x.permission, Permission) for x in bindings)

for binding in bindings:
    rule = get_integration_permission_rule_v098(binding.capability_id)
    assert rule is not None
    assert rule.provider_id == binding.provider_id
    assert rule.allowed is True
    assert binding.permission is rule.permission
    assert binding.confirmation_required is rule.confirmation_required

assert registry.skills_for_capability(
    "email.provider",
    "email.search",
) == ("personal.research",)

# Same capability may be referenced by more than one skill without creating
# a second capability authority.
second = SkillManifest(
    skill_id="mail.reader",
    display_name="Mail Reader",
    skill_version="1.0.0",
    capabilities=(SkillCapabilityRef("email.provider", "email.search"),),
)
registry.register_manifest(second)
assert registry.skills_for_capability(
    "email.provider",
    "email.search",
) == ("mail.reader", "personal.research")

# Duplicate skill id fails closed.
try:
    registry.register_manifest(second)
    raise AssertionError("duplicate skill id must fail")
except DuplicateSkillError:
    pass

# Unknown capability fails closed.
unknown = SkillManifest(
    skill_id="unknown.cap",
    display_name="Unknown",
    skill_version="1.0.0",
    capabilities=(SkillCapabilityRef("email.provider", "email.unknown"),),
)
try:
    registry.register_manifest(unknown)
    raise AssertionError("unknown capability must fail")
except UnknownSkillCapabilityError:
    pass

# Explicitly denied v0.9.8 capability can never enter a skill registry.
denied = SkillManifest(
    skill_id="unsafe.browser",
    display_name="Unsafe Browser",
    skill_version="1.0.0",
    capabilities=(
        SkillCapabilityRef(
            "browser.provider",
            "browser.captcha_bypass",
        ),
    ),
)
try:
    registry.register_manifest(denied)
    raise AssertionError("denied capability must fail")
except DeniedSkillCapabilityError:
    pass

# Registration is metadata/indexing only. Execution remains outside this layer.
public = {
    name
    for name, member in inspect.getmembers(
        SkillCapabilityRegistryV100,
        predicate=inspect.isfunction,
    )
    if not name.startswith("_")
}
assert public == {
    "register_manifest",
    "unregister_manifest",
    "get_manifest",
    "list_manifests",
    "list_bindings",
    "resolve_binding",
    "skills_for_capability",
}
assert not ({"execute", "run", "invoke", "dispatch"} & public)

assert registry.unregister_manifest("mail.reader") is True
assert registry.unregister_manifest("mail.reader") is False
assert registry.skills_for_capability(
    "email.provider",
    "email.search",
) == ("personal.research",)

print("[PASS] Skill Manifest & Capability Registry v1.0.0")
print("[PASS] Skill manifests validate identifiers, semver and immutable metadata")
print("[PASS] registry references existing IntegrationCapability authority")
print("[PASS] registry references existing Permission/v0.9.8 policy authority")
print("[PASS] duplicate/unknown/denied capabilities fail closed")
print("[PASS] multiple skills may reference one canonical capability")
print("[PASS] skill registry has no execution authority")
