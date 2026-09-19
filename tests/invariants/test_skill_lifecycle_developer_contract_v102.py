from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from integrations.registry import IntegrationCapability
from security.permissions import Permission
from skills.developer_contract import (
    SkillDeveloperContractError,
    SkillDeveloperContractV102,
    build_skill_developer_contract_v102,
)
from skills.lifecycle import (
    SkillAlreadyActiveError,
    SkillAlreadyInstalledError,
    SkillLifecycleManagerV102,
    SkillNotActiveError,
    SkillNotInstalledError,
)
from skills.manifest import SkillCapabilityRef, SkillManifest
from skills.registry import SkillCapabilityRegistryV100
from skills.runtime import (
    SecureSkillRuntimeV101,
    UnknownSkillRuntimeError,
)


def cap(capability_id, *, confirmation=False, risk="LOW", side="read_only"):
    return IntegrationCapability(
        capability_id=capability_id,
        action=capability_id.split(".", 1)[1],
        description="v1.0.2 lifecycle acceptance " + capability_id,
        risk_tier=risk,
        requires_confirmation=bool(confirmation),
        side_effect_class=side,
        evidence_required=True,
    )


class FakeIntegrationRegistry:
    def __init__(self):
        self.capabilities = {
            ("browser.provider", "browser.search"): cap("browser.search"),
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
        return SimpleNamespace(
            request_id=request.request_id,
            provider_id=request.provider_id,
            capability_id=request.capability_id,
            status="success",
            ok=True,
            receipt_id="receipt-" + request.request_id,
            output={"echo": dict(request.params)},
            error=None,
            evidence_refs=(),
        )


manifest = SkillManifest(
    skill_id="developer.sample",
    display_name="Developer Sample",
    skill_version="1.0.2",
    capabilities=(
        SkillCapabilityRef("browser.provider", "browser.search"),
    ),
)

contract = build_skill_developer_contract_v102(
    manifest=manifest,
    payload={
        "min_aura_version": "1.0.0",
        "max_aura_version": "1.0.9",
        "metadata": {
            "publisher": "AURA acceptance",
        },
    },
)

assert isinstance(contract, SkillDeveloperContractV102)
assert contract.supports_aura_version("1.0.1")
assert contract.supports_aura_version("1.0.2")
assert not contract.supports_aura_version("0.9.9")
assert not contract.supports_aura_version("1.1.0")
assert contract.execution_model == "secure_runtime_v101"
assert contract.install_scope == "metadata_only"
assert contract.dynamic_code is False

try:
    contract.metadata["unsafe"] = True
    raise AssertionError("developer metadata must be immutable")
except TypeError:
    pass

# Fail-closed developer contract.
for payload in (
    {
        "min_aura_version": "1.0.0",
        "entrypoint": "malicious.module:run",
    },
    {
        "min_aura_version": "1.0.0",
        "dynamic_code": True,
    },
    {
        "min_aura_version": "1.0.0",
        "execution_model": "direct_python",
    },
    {
        "min_aura_version": "1.0.0",
        "install_scope": "system",
    },
    {
        "min_aura_version": "1.0.5",
        "max_aura_version": "1.0.1",
    },
):
    try:
        build_skill_developer_contract_v102(
            manifest=manifest,
            payload=payload,
        )
        raise AssertionError("unsafe developer contract must fail")
    except SkillDeveloperContractError:
        pass

fake = FakeIntegrationRegistry()
skill_registry = SkillCapabilityRegistryV100(
    integration_registry=fake,
)
runtime = SecureSkillRuntimeV101(
    skill_registry=skill_registry,
    integration_registry=fake,
    granted_permissions=(Permission.WEB_READ,),
)
lifecycle = SkillLifecycleManagerV102(
    skill_registry=skill_registry,
    secure_runtime=runtime,
    aura_version="1.0.2",
)

# Install is metadata only.
record = lifecycle.install(contract)
assert record.state == "installed"
assert lifecycle.is_active("developer.sample") is False
assert skill_registry.get_manifest("developer.sample") is None
assert fake.calls == []

try:
    lifecycle.install(contract)
    raise AssertionError("duplicate install must fail")
except SkillAlreadyInstalledError:
    pass

# Not active means SecureSkillRuntime cannot resolve the skill.
try:
    runtime.execute(
        skill_id="developer.sample",
        provider_id="browser.provider",
        capability_id="browser.search",
        params={"query": "inactive"},
    )
    raise AssertionError("inactive skill must not execute")
except UnknownSkillRuntimeError:
    pass
assert fake.calls == []

# Activate registers only the Skill manifest.
active = lifecycle.activate("developer.sample")
assert active.state == "active"
assert lifecycle.is_active("developer.sample") is True
assert skill_registry.get_manifest("developer.sample") is manifest
assert fake.calls == []

try:
    lifecycle.activate("developer.sample")
    raise AssertionError("duplicate activate must fail")
except SkillAlreadyActiveError:
    pass

# Actual execution remains SecureSkillRuntimeV101 -> IntegrationRegistry.
result = lifecycle.runtime().execute(
    skill_id="developer.sample",
    provider_id="browser.provider",
    capability_id="browser.search",
    params={"query": "active"},
    request_id="v102-active",
)
assert result.status == "success"
assert len(fake.calls) == 1
assert fake.calls[-1]["request"].origin == (
    "skill.runtime.v101:developer.sample"
)

# Deactivate unregisters Skill only; future runtime resolution is denied.
inactive = lifecycle.deactivate("developer.sample")
assert inactive.state == "installed"
assert lifecycle.is_active("developer.sample") is False
assert skill_registry.get_manifest("developer.sample") is None

try:
    lifecycle.deactivate("developer.sample")
    raise AssertionError("double deactivate must fail")
except SkillNotActiveError:
    pass

before = len(fake.calls)
try:
    runtime.execute(
        skill_id="developer.sample",
        provider_id="browser.provider",
        capability_id="browser.search",
        params={"query": "blocked"},
    )
    raise AssertionError("deactivated skill must not execute")
except UnknownSkillRuntimeError:
    pass
assert len(fake.calls) == before

# Reactivate then uninstall: unregister skill metadata only.
lifecycle.activate("developer.sample")
assert lifecycle.uninstall("developer.sample") is True
assert lifecycle.uninstall("developer.sample") is False
assert lifecycle.get_record("developer.sample") is None
assert lifecycle.is_active("developer.sample") is False
assert skill_registry.get_manifest("developer.sample") is None

try:
    lifecycle.activate("developer.sample")
    raise AssertionError("uninstalled skill cannot activate")
except SkillNotInstalledError:
    pass

# Incompatible contract cannot install.
future_manifest = SkillManifest(
    skill_id="future.skill",
    display_name="Future Skill",
    skill_version="2.0.0",
    capabilities=(
        SkillCapabilityRef("browser.provider", "browser.search"),
    ),
)
future_contract = SkillDeveloperContractV102(
    manifest=future_manifest,
    min_aura_version="2.0.0",
)
try:
    lifecycle.install(future_contract)
    raise AssertionError("incompatible Aura version must fail")
except SkillDeveloperContractError:
    pass
assert skill_registry.get_manifest("future.skill") is None

# Narrow public lifecycle API, no execute/run/invoke/dispatch.
public = {
    name
    for name, member in inspect.getmembers(
        SkillLifecycleManagerV102,
        predicate=inspect.isfunction,
    )
    if not name.startswith("_")
}
assert public == {
    "install",
    "activate",
    "deactivate",
    "uninstall",
    "get_record",
    "list_records",
    "is_active",
    "runtime",
}
assert not ({"execute", "run", "invoke", "dispatch"} & public)

# Static trust-boundary guard for both new files.
# Comments/docstrings may name protected authorities; executable AST references may not.
for rel in ("skills/lifecycle.py", "skills/developer_contract.py"):
    path = ROOT / rel
    source = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(path))

    forbidden_roots = {
        "subprocess",
        "socket",
        "requests",
        "httpx",
        "urllib",
        "runpy",
        "importlib",
        "integrations",
        "action_receipts",
        "security",
        "mission_engine",
    }
    forbidden_authority_names = {
        "IntegrationRegistry",
        "ActionReceiptService",
        "SecurityPolicyEngine",
        "MissionEngine",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                assert item.name.split(".", 1)[0] not in forbidden_roots
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".", 1)[0] not in forbidden_roots
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {
                "eval",
                "exec",
                "compile",
                "__import__",
            }
        elif isinstance(node, ast.Name):
            assert node.id not in forbidden_authority_names
        elif isinstance(node, ast.Attribute):
            assert node.attr not in forbidden_authority_names

print("[PASS] Skill Lifecycle & Developer Contract v1.0.2")
print("[PASS] install validates metadata/version only")
print("[PASS] activation/deactivation modifies Skill Registry state only")
print("[PASS] inactive/deactivated/uninstalled skills cannot resolve through SecureSkillRuntimeV101")
print("[PASS] uninstall never touches canonical integration providers")
print("[PASS] developer contract rejects unknown fields, dynamic code and alternate execution models")
print("[PASS] no direct Python/subprocess/network/security/receipt authority is added")
