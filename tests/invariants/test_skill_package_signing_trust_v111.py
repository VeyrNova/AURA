from __future__ import annotations

import ast
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from integrations.registry import IntegrationCapability
from security.permissions import Permission
from skills.catalog import LocalSkillCatalogV110
from skills.developer_contract import SkillDeveloperContractV102
from skills.lifecycle import SkillLifecycleManagerV102
from skills.manifest import SkillCapabilityRef, SkillManifest
from skills.package import encode_skill_package_v110
from skills.registry import SkillCapabilityRegistryV100
from skills.runtime import SecureSkillRuntimeV101
from skills.signing import (
    SignedSkillPackageEnvelopeV111,
    SkillPackageSignatureError,
    ed25519_public_key_bytes_v111,
    sign_skill_package_v111,
)
from skills.trust import (
    DisabledTrustedKeyError,
    LocalSkillTrustStoreV111,
    RevokedTrustedKeyError,
    TrustedPublisherKeyV111,
    UnknownTrustedKeyError,
    UnknownTrustedPublisherError,
)
from skills.trusted_distribution import (
    TrustedSkillDistributionServiceV111,
)


def cap(capability_id):
    return IntegrationCapability(
        capability_id=capability_id,
        action=capability_id.split(".", 1)[1],
        description="v1.1.1 trust acceptance",
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

    def resolve_capability(self, provider_id, capability_id):
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
                "user_confirmed": bool(user_confirmed),
            }
        )
        return SimpleNamespace(
            request_id=request.request_id,
            provider_id=request.provider_id,
            capability_id=request.capability_id,
            status="success",
            ok=True,
            receipt_id="v111-" + request.request_id,
            output={"params": dict(request.params)},
            error=None,
            evidence_refs=(),
        )


manifest = SkillManifest(
    skill_id="trusted.alpha",
    display_name="Trusted Alpha",
    skill_version="1.1.1",
    capabilities=(
        SkillCapabilityRef(
            "browser.provider",
            "browser.search",
        ),
    ),
    description="Signed skill package acceptance",
)
contract = SkillDeveloperContractV102(
    manifest=manifest,
    min_aura_version="1.0.0",
    max_aura_version="1.9.9",
    metadata={"publisher": "acceptance"},
)
artifact = encode_skill_package_v110(contract)

private_key = Ed25519PrivateKey.generate()
public_key_bytes = ed25519_public_key_bytes_v111(
    private_key.public_key()
)

envelope = sign_skill_package_v111(
    artifact=artifact,
    publisher_id="publisher.alpha",
    key_id="main.2026",
    private_key=private_key,
)
assert isinstance(
    envelope,
    SignedSkillPackageEnvelopeV111,
)
assert len(envelope.signature) == 64

trust_store = LocalSkillTrustStoreV111()
trust_store.add_key(
    TrustedPublisherKeyV111(
        publisher_id="publisher.alpha",
        key_id="main.2026",
        public_key_bytes=public_key_bytes,
    )
)
verified = trust_store.verify(envelope)
assert verified.publisher_id == "publisher.alpha"
assert verified.key_id == "main.2026"

# Unknown publisher is denied.
unknown_publisher = sign_skill_package_v111(
    artifact=artifact,
    publisher_id="publisher.unknown",
    key_id="main.2026",
    private_key=private_key,
)
try:
    trust_store.verify(unknown_publisher)
    raise AssertionError("unknown publisher must deny")
except UnknownTrustedPublisherError:
    pass

# Known publisher + unknown key is denied.
unknown_key = sign_skill_package_v111(
    artifact=artifact,
    publisher_id="publisher.alpha",
    key_id="unknown.key",
    private_key=private_key,
)
try:
    trust_store.verify(unknown_key)
    raise AssertionError("unknown key must deny")
except UnknownTrustedKeyError:
    pass

# Wrong signature is denied.
other_private_key = Ed25519PrivateKey.generate()
bad_signature = sign_skill_package_v111(
    artifact=artifact,
    publisher_id="publisher.alpha",
    key_id="main.2026",
    private_key=other_private_key,
)
try:
    trust_store.verify(bad_signature)
    raise AssertionError("wrong signature must deny")
except SkillPackageSignatureError:
    pass

# Disabled key denies.
trust_store.set_enabled(
    "publisher.alpha",
    "main.2026",
    False,
)
try:
    trust_store.verify(envelope)
    raise AssertionError("disabled key must deny")
except DisabledTrustedKeyError:
    pass

trust_store.set_enabled(
    "publisher.alpha",
    "main.2026",
    True,
)
assert trust_store.verify(envelope).enabled is True

# Trusted distribution verifies before catalog acceptance/install.
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
    aura_version="1.1.1",
)
catalog = LocalSkillCatalogV110()
trusted_distribution = TrustedSkillDistributionServiceV111(
    catalog=catalog,
    lifecycle=lifecycle,
    trust_store=trust_store,
)

acceptance = trusted_distribution.accept(envelope)
assert acceptance.skill_id == "trusted.alpha"
assert acceptance.publisher_id == "publisher.alpha"
assert catalog.get("trusted.alpha") is not None
assert lifecycle.get_record("trusted.alpha") is None

installed = trusted_distribution.install("trusted.alpha")
assert installed.state == "installed"
assert lifecycle.is_active("trusted.alpha") is False
assert skill_registry.get_manifest("trusted.alpha") is None

# Activation/execution remain existing authorities.
lifecycle.activate("trusted.alpha")
result = runtime.execute(
    skill_id="trusted.alpha",
    provider_id="browser.provider",
    capability_id="browser.search",
    params={"query": "trusted"},
    request_id="v111-trusted",
)
assert result.status == "success"
assert integration_registry.calls[-1]["request"].origin == (
    "skill.runtime.v101:trusted.alpha"
)

# Key rotation/revocation is explicit and fail-closed.
trust_store.revoke_key(
    "publisher.alpha",
    "main.2026",
)
try:
    trust_store.verify(envelope)
    raise AssertionError("revoked key must deny")
except RevokedTrustedKeyError:
    pass

new_private_key = Ed25519PrivateKey.generate()
new_public_key_bytes = ed25519_public_key_bytes_v111(
    new_private_key.public_key()
)
trust_store.add_key(
    TrustedPublisherKeyV111(
        publisher_id="publisher.alpha",
        key_id="main.2027",
        public_key_bytes=new_public_key_bytes,
    )
)
rotated_envelope = sign_skill_package_v111(
    artifact=artifact,
    publisher_id="publisher.alpha",
    key_id="main.2027",
    private_key=new_private_key,
)
assert trust_store.verify(rotated_envelope).key_id == "main.2027"

# Static trust-boundary guard.
for rel in (
    "skills/signing.py",
    "skills/trust.py",
    "skills/trusted_distribution.py",
):
    path = ROOT / rel
    source = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(path))

    forbidden_roots = {
        "os",
        "pathlib",
        "shutil",
        "subprocess",
        "socket",
        "requests",
        "httpx",
        "urllib",
        "runpy",
        "importlib",
        "pickle",
        "marshal",
        "shelve",
        "zipfile",
        "tarfile",
        "integrations",
        "security",
        "action_receipts",
        "mission_engine",
    }
    forbidden_names = {
        "IntegrationRegistry",
        "SecurityPolicyEngine",
        "ActionReceiptService",
        "MissionEngine",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                assert (
                    item.name.split(".", 1)[0]
                    not in forbidden_roots
                )
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert (
                node.module.split(".", 1)[0]
                not in forbidden_roots
            )
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {
                "eval",
                "exec",
                "compile",
                "__import__",
            }
        elif isinstance(node, ast.Name):
            assert node.id not in forbidden_names

    assert "private_bytes(" not in source

print("[PASS] Skill Package Signing & Trust v1.1.1")
print("[PASS] Ed25519 signs exact canonical v1.1.0 package bytes")
print("[PASS] unknown publisher/key, invalid signature, disabled/revoked key fail closed")
print("[PASS] trusted distribution verifies before catalog acceptance and install")
print("[PASS] private keys are never serialized or persisted by the v1.1.1 layer")
print("[PASS] lifecycle remains SkillLifecycleManagerV102 authority")
print("[PASS] execution remains SecureSkillRuntimeV101 authority")
print("[PASS] no network/filesystem/dynamic-code authority added")
