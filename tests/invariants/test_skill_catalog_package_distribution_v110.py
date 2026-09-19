from __future__ import annotations

import ast
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from integrations.registry import IntegrationCapability
from security.permissions import Permission
from skills.catalog import (
    DuplicateSkillCatalogEntryError,
    LocalSkillCatalogV110,
)
from skills.developer_contract import (
    SkillDeveloperContractError,
    SkillDeveloperContractV102,
)
from skills.distribution import (
    SkillDistributionServiceV110,
)
from skills.lifecycle import (
    SkillLifecycleManagerV102,
)
from skills.manifest import (
    SkillCapabilityRef,
    SkillManifest,
)
from skills.package import (
    SkillPackageIntegrityError,
    SkillPackageMetadataError,
    SkillPackageSchemaError,
    decode_skill_package_v110,
    encode_skill_package_v110,
)
from skills.registry import SkillCapabilityRegistryV100
from skills.runtime import (
    SecureSkillRuntimeV101,
    UnknownSkillRuntimeError,
)


def cap(capability_id):
    return IntegrationCapability(
        capability_id=capability_id,
        action=capability_id.split(".", 1)[1],
        description="v1.1 package acceptance",
        risk_tier="LOW",
        requires_confirmation=False,
        side_effect_class="read_only",
        evidence_required=True,
    )


class FakeIntegrationRegistry:
    def __init__(self):
        self.capabilities = {
            (
                "browser.provider",
                "browser.search",
            ): cap("browser.search"),
        }
        self.calls = []

    def resolve_capability(
        self,
        provider_id,
        capability_id,
    ):
        return self.capabilities.get(
            (provider_id, capability_id)
        )

    def execute_integration(
        self,
        request,
        *,
        user_confirmed=False,
    ):
        self.calls.append(
            {
                "request": request,
                "user_confirmed": bool(
                    user_confirmed
                ),
            }
        )
        return SimpleNamespace(
            request_id=request.request_id,
            provider_id=request.provider_id,
            capability_id=request.capability_id,
            status="success",
            ok=True,
            receipt_id="v110-" + request.request_id,
            output={"params": dict(request.params)},
            error=None,
            evidence_refs=(),
        )


def make_contract(skill_id, display_name):
    manifest = SkillManifest(
        skill_id=skill_id,
        display_name=display_name,
        skill_version="1.1.0",
        capabilities=(
            SkillCapabilityRef(
                "browser.provider",
                "browser.search",
            ),
        ),
        description="Declarative package acceptance",
        metadata={
            "tags": ["local", "safe"],
            "priority": 1,
            "nested": {
                "enabled": True,
                "note": None,
            },
        },
    )
    return SkillDeveloperContractV102(
        manifest=manifest,
        min_aura_version="1.0.0",
        max_aura_version="1.9.9",
        metadata={
            "publisher": "AURA acceptance",
            "rating": 4.5,
        },
    )


contract = make_contract(
    "catalog.alpha",
    "Catalog Alpha",
)

# Deterministic canonical package bytes and digest.
artifact_a = encode_skill_package_v110(contract)
artifact_b = encode_skill_package_v110(contract)
assert artifact_a.package_bytes == artifact_b.package_bytes
assert artifact_a.sha256 == artifact_b.sha256
assert artifact_a.skill_id == "catalog.alpha"

decoded = decode_skill_package_v110(
    artifact_a.package_bytes,
    expected_sha256=artifact_a.sha256,
)
assert decoded.manifest.skill_id == contract.manifest.skill_id
assert decoded.manifest.display_name == contract.manifest.display_name
assert decoded.manifest.skill_version == contract.manifest.skill_version
assert tuple(
    (x.provider_id, x.capability_id)
    for x in decoded.manifest.capabilities
) == (
    ("browser.provider", "browser.search"),
)
assert dict(decoded.manifest.metadata) == dict(
    contract.manifest.metadata
)
assert dict(decoded.metadata) == dict(
    contract.metadata
)

# Tampered bytes fail integrity before install.
tampered = bytearray(artifact_a.package_bytes)
tampered[-1] = (
    ord(" ")
    if tampered[-1] != ord(" ")
    else ord("\n")
)
try:
    decode_skill_package_v110(
        bytes(tampered),
        expected_sha256=artifact_a.sha256,
    )
    raise AssertionError("tamper must fail")
except SkillPackageIntegrityError:
    pass

# Unknown or executable-looking top-level fields are denied.
payload = json.loads(
    artifact_a.package_bytes.decode("utf-8")
)
payload["entrypoint"] = "evil.module:run"
bad = json.dumps(
    payload,
    sort_keys=True,
    separators=(",", ":"),
).encode("utf-8")
try:
    decode_skill_package_v110(bad)
    raise AssertionError("unknown field must fail")
except SkillPackageSchemaError:
    pass

# Dynamic code remains denied by the existing developer contract.
payload = json.loads(
    artifact_a.package_bytes.decode("utf-8")
)
payload["developer_contract"]["dynamic_code"] = True
bad_dynamic = json.dumps(
    payload,
    sort_keys=True,
    separators=(",", ":"),
).encode("utf-8")
try:
    decode_skill_package_v110(bad_dynamic)
    raise AssertionError("dynamic code must fail")
except SkillDeveloperContractError:
    pass

# Non JSON-safe metadata and non-finite numbers fail closed.
for unsafe in (
    object(),
    float("nan"),
    float("inf"),
):
    unsafe_manifest = SkillManifest(
        skill_id="unsafe.meta",
        display_name="Unsafe Meta",
        skill_version="1.1.0",
        capabilities=(
            SkillCapabilityRef(
                "browser.provider",
                "browser.search",
            ),
        ),
        metadata={"unsafe": unsafe},
    )
    unsafe_contract = SkillDeveloperContractV102(
        manifest=unsafe_manifest,
        min_aura_version="1.0.0",
    )
    try:
        encode_skill_package_v110(
            unsafe_contract
        )
        raise AssertionError(
            "unsafe metadata must fail"
        )
    except SkillPackageMetadataError:
        pass

# Local catalog is deterministic and duplicate-denying.
catalog = LocalSkillCatalogV110()
entry_alpha = catalog.add_package(artifact_a)
assert entry_alpha.skill_id == "catalog.alpha"

try:
    catalog.add_package(artifact_a)
    raise AssertionError("duplicate skill_id must fail")
except DuplicateSkillCatalogEntryError:
    pass

contract_beta = make_contract(
    "catalog.beta",
    "Catalog Beta",
)
artifact_beta = encode_skill_package_v110(
    contract_beta
)
catalog.add_package(artifact_beta)

assert tuple(
    entry.skill_id
    for entry in catalog.list_entries()
) == (
    "catalog.alpha",
    "catalog.beta",
)

# Distribution publishes/installs declarative contracts only.
integration_registry = FakeIntegrationRegistry()
skill_registry = SkillCapabilityRegistryV100(
    integration_registry=integration_registry,
)
runtime = SecureSkillRuntimeV101(
    skill_registry=skill_registry,
    integration_registry=integration_registry,
    granted_permissions=(Permission.WEB_READ,),
)
lifecycle = SkillLifecycleManagerV102(
    skill_registry=skill_registry,
    secure_runtime=runtime,
    aura_version="1.1.0",
)
dist_catalog = LocalSkillCatalogV110()
distribution = SkillDistributionServiceV110(
    catalog=dist_catalog,
    lifecycle=lifecycle,
)

distribution.publish(contract)
assert dist_catalog.get("catalog.alpha") is not None
assert lifecycle.get_record("catalog.alpha") is None

installed = distribution.install(
    "catalog.alpha"
)
assert installed.state == "installed"
assert lifecycle.is_active("catalog.alpha") is False
assert skill_registry.get_manifest(
    "catalog.alpha"
) is None
assert integration_registry.calls == []

# Installed but inactive package cannot execute.
try:
    runtime.execute(
        skill_id="catalog.alpha",
        provider_id="browser.provider",
        capability_id="browser.search",
        params={"query": "inactive"},
    )
    raise AssertionError(
        "inactive package must not execute"
    )
except UnknownSkillRuntimeError:
    pass

# Existing lifecycle remains sole activation authority.
lifecycle.activate("catalog.alpha")
result = runtime.execute(
    skill_id="catalog.alpha",
    provider_id="browser.provider",
    capability_id="browser.search",
    params={"query": "active"},
    request_id="v110-active",
)
assert result.status == "success"
assert len(integration_registry.calls) == 1
assert (
    integration_registry.calls[-1]["request"].origin
    == "skill.runtime.v101:catalog.alpha"
)

# Unpublish only affects catalog, not installed lifecycle metadata.
assert distribution.unpublish(
    "catalog.alpha"
) is True
assert dist_catalog.get("catalog.alpha") is None
assert lifecycle.get_record(
    "catalog.alpha"
) is not None

# Static trust-boundary guard.
for rel in (
    "skills/package.py",
    "skills/catalog.py",
    "skills/distribution.py",
):
    path = ROOT / rel
    source = path.read_text(
        encoding="utf-8-sig"
    )
    tree = ast.parse(
        source,
        filename=str(path),
    )

    forbidden_roots = {
        "pickle",
        "marshal",
        "shelve",
        "zipfile",
        "tarfile",
        "runpy",
        "importlib",
        "subprocess",
        "socket",
        "requests",
        "httpx",
        "urllib",
        "pathlib",
        "os",
        "shutil",
        "integrations",
        "security",
        "action_receipts",
        "mission_engine",
    }
    forbidden_names = {
        "IntegrationRegistry",
        "ActionReceiptService",
        "SecurityPolicyEngine",
        "MissionEngine",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                assert (
                    item.name.split(".", 1)[0]
                    not in forbidden_roots
                )
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
        ):
            assert (
                node.module.split(".", 1)[0]
                not in forbidden_roots
            )
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
        ):
            assert node.func.id not in {
                "eval",
                "exec",
                "compile",
                "__import__",
            }
        elif isinstance(node, ast.Name):
            assert node.id not in forbidden_names

print("[PASS] Skill Catalog / Package / Distribution v1.1.0")
print("[PASS] package format is canonical JSON UTF-8")
print("[PASS] SHA-256 integrity is deterministic")
print("[PASS] tampering and unknown package fields fail closed")
print("[PASS] non-JSON-safe metadata is rejected")
print("[PASS] catalog is local, deterministic and duplicate-denying")
print("[PASS] distribution installs through existing lifecycle only")
print("[PASS] activation remains SkillLifecycleManagerV102 authority")
print("[PASS] execution remains SecureSkillRuntimeV101 authority")
print("[PASS] no archive, filesystem, dynamic import, process or network package transport")
