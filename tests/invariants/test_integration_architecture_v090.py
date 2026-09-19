from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import AURA_VERSION
from action_receipts import ActionReceiptService, ActionReceiptStore
from integrations import (
    INTEGRATION_RESULT_STATUSES,
    IntegrationCapability,
    IntegrationManifest,
    IntegrationMissionToolAdapter,
    IntegrationProviderState,
    IntegrationRegistry,
    IntegrationRequest,
    ProviderRegistrationError,
)

assert AURA_VERSION == '0.9.4', AURA_VERSION

assert INTEGRATION_RESULT_STATUSES == (
    "waiting_confirmation",
    "denied",
    "succeeded",
    "failed",
    "cancelled",
)

class FakeSecurity:
    def __init__(self):
        self.calls = []

    def authorize(self, action, params, user_confirmed=False):
        self.calls.append(
            {
                "action": action,
                "params": dict(params),
                "user_confirmed": bool(user_confirmed),
            }
        )
        if action == "synthetic.write" and not user_confirmed:
            return "REQUIRE_CONFIRMATION"
        if action == "synthetic.deny":
            return "DENY"
        return "ALLOW"

class ExplodingSecurity:
    def authorize(self, action, params, user_confirmed=False):
        raise RuntimeError("synthetic security exception")

class SyntheticProvider:
    def __init__(self):
        self.calls = []
        self._manifest = IntegrationManifest(
            provider_id="synthetic.provider",
            display_name="Synthetic Provider",
            provider_version="1",
            capabilities=(
                IntegrationCapability(
                    capability_id="synthetic.read",
                    action="synthetic.read",
                    description="Synthetic read",
                    risk_tier="low",
                    requires_confirmation=False,
                    side_effect_class="read",
                ),
                IntegrationCapability(
                    capability_id="synthetic.write",
                    action="synthetic.write",
                    description="Synthetic write",
                    risk_tier="medium",
                    requires_confirmation=True,
                    side_effect_class="write",
                ),
                IntegrationCapability(
                    capability_id="synthetic.deny",
                    action="synthetic.deny",
                    description="Synthetic denied capability",
                    risk_tier="high",
                    requires_confirmation=True,
                    side_effect_class="write",
                ),
                IntegrationCapability(
                    capability_id="synthetic.fail",
                    action="synthetic.fail",
                    description="Synthetic failure",
                    risk_tier="low",
                    requires_confirmation=False,
                    side_effect_class="compute",
                ),
            ),
            metadata={"synthetic": True},
        )

    @property
    def manifest(self):
        return self._manifest

    def execute(self, request):
        self.calls.append(request.request_id)
        if request.capability_id == "synthetic.fail":
            raise RuntimeError("synthetic provider failure")
        return {
            "ok": True,
            "capability_id": request.capability_id,
            "evidence_refs": ["synthetic-evidence"],
        }

    def health_snapshot(self):
        return {"available": True, "health_state": "healthy"}

with tempfile.TemporaryDirectory(prefix="aura_v090_integrations_") as td:
    db = Path(td) / "receipts.db"
    receipt_service = ActionReceiptService(
        store=ActionReceiptStore(db)
    )
    security = FakeSecurity()
    registry = IntegrationRegistry(
        security_engine=security,
        receipt_service=receipt_service,
    )
    provider = SyntheticProvider()

    state = registry.register_provider(provider)
    assert isinstance(state, IntegrationProviderState)
    assert state.provider_id == "synthetic.provider"

    try:
        registry.register_provider(provider)
    except ProviderRegistrationError:
        pass
    else:
        raise AssertionError("duplicate provider registration must fail")

    assert len(registry.list_providers()) == 1
    assert registry.get_provider("synthetic.provider") is provider
    assert registry.resolve_capability(
        "synthetic.provider",
        "synthetic.read",
    ).action == "synthetic.read"

    context = registry.build_integration_context(
        "synthetic.provider",
        "synthetic.read",
    )
    assert context is not None
    assert context.available is True
    assert context.provider == "synthetic.provider"

    request_a = IntegrationRequest.create(
        provider_id="synthetic.provider",
        capability_id="synthetic.read",
        params={"query": "hello"},
        origin="synthetic.test",
    )
    request_b = IntegrationRequest.create(
        provider_id="synthetic.provider",
        capability_id="synthetic.read",
        params={"query": "hello"},
        origin="synthetic.test",
    )
    assert request_a.request_id == request_b.request_id

    success = registry.execute_integration(request_a)
    assert success.status == "succeeded"
    assert success.ok is True
    assert success.evidence_refs == ("synthetic-evidence",)
    success_receipt = receipt_service.get_receipt(success.receipt_id)
    assert success_receipt.status == "succeeded"
    assert success_receipt.policy_decision == "ALLOW"

    before = len(provider.calls)
    unknown_provider = registry.execute_integration(
        IntegrationRequest.create(
            provider_id="missing.provider",
            capability_id="synthetic.read",
            params={},
            origin="synthetic.test",
        )
    )
    assert unknown_provider.status == "denied"
    assert unknown_provider.error == "unknown_provider"
    assert len(provider.calls) == before

    unknown_capability = registry.execute_integration(
        IntegrationRequest.create(
            provider_id="synthetic.provider",
            capability_id="missing.capability",
            params={},
            origin="synthetic.test",
        )
    )
    assert unknown_capability.status == "denied"
    assert unknown_capability.error == "unknown_capability"
    assert len(provider.calls) == before

    write_request = IntegrationRequest.create(
        provider_id="synthetic.provider",
        capability_id="synthetic.write",
        params={"value": 1},
        origin="synthetic.test",
    )
    waiting = registry.execute_integration(write_request)
    assert waiting.status == "waiting_confirmation"
    assert len(provider.calls) == before
    assert receipt_service.get_receipt(
        waiting.receipt_id
    ).confirmation_state == "pending"

    confirmed = registry.execute_integration(
        write_request,
        user_confirmed=True,
    )
    assert confirmed.status == "succeeded"
    assert confirmed.receipt_id == waiting.receipt_id
    assert len(provider.calls) == before + 1

    before = len(provider.calls)
    denied = registry.execute_integration(
        IntegrationRequest.create(
            provider_id="synthetic.provider",
            capability_id="synthetic.deny",
            params={},
            origin="synthetic.test",
        )
    )
    assert denied.status == "denied"
    assert len(provider.calls) == before

    failed = registry.execute_integration(
        IntegrationRequest.create(
            provider_id="synthetic.provider",
            capability_id="synthetic.fail",
            params={},
            origin="synthetic.test",
        )
    )
    assert failed.status == "failed"
    assert failed.error == "RuntimeError"
    assert receipt_service.get_receipt(failed.receipt_id).status == "failed"
    assert registry.health_snapshot(
        "synthetic.provider"
    )[0].health_state == "degraded"

    healed = registry.execute_integration(
        IntegrationRequest.create(
            provider_id="synthetic.provider",
            capability_id="synthetic.read",
            params={"heal": True},
            origin="synthetic.test",
        )
    )
    assert healed.status == "succeeded"
    assert registry.health_snapshot(
        "synthetic.provider"
    )[0].health_state == "healthy"

    secure_db = Path(td) / "secure.db"
    secure_registry = IntegrationRegistry(
        security_engine=ExplodingSecurity(),
        receipt_service=ActionReceiptService(
            store=ActionReceiptStore(secure_db)
        ),
    )
    secure_provider = SyntheticProvider()
    secure_registry.register_provider(secure_provider)
    before_secure = len(secure_provider.calls)
    security_denied = secure_registry.execute_integration(
        IntegrationRequest.create(
            provider_id="synthetic.provider",
            capability_id="synthetic.read",
            params={},
            origin="synthetic.security",
        )
    )
    assert security_denied.status == "denied"
    assert len(secure_provider.calls) == before_secure

    class FakeToolCall:
        params = {"query": "mission-boundary"}

    adapter = IntegrationMissionToolAdapter(
        registry=registry,
        provider_id="synthetic.provider",
        capability_id="synthetic.read",
    )
    assert adapter(FakeToolCall())["ok"] is True

    assert registry.unregister_provider("synthetic.provider") is True
    assert registry.get_provider("synthetic.provider") is None
    assert registry.unregister_provider("synthetic.provider") is False

    db.unlink()
    assert not db.exists()
    secure_db.unlink()
    assert not secure_db.exists()

print("[PASS] Integration Architecture v0.9.0 synthetic lifecycle invariant")
raise SystemExit(0)
