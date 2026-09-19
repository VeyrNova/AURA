"""AURA v0.9.0 provider-neutral Personal Integration Architecture."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable

from action_receipts import ActionReceiptService, CapabilityContext

INTEGRATION_RESULT_STATUSES = (
    "waiting_confirmation",
    "denied",
    "succeeded",
    "failed",
    "cancelled",
)

class IntegrationError(RuntimeError):
    pass

class ProviderRegistrationError(IntegrationError):
    pass

class UnknownProviderError(IntegrationError):
    pass

class UnknownCapabilityError(IntegrationError):
    pass

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )

def _stable_id(prefix: str, *parts: Any) -> str:
    return prefix + hashlib.sha256(
        _canonical_json(parts).encode("utf-8")
    ).hexdigest()[:24]

@dataclass(frozen=True)
class IntegrationCapability:
    capability_id: str
    action: str
    description: str
    risk_tier: str
    requires_confirmation: bool
    side_effect_class: str
    evidence_required: bool = True

    def __post_init__(self) -> None:
        if not self.capability_id.strip():
            raise ValueError("capability_id is required")
        if not self.action.strip():
            raise ValueError("action is required")

@dataclass(frozen=True)
class IntegrationManifest:
    provider_id: str
    display_name: str
    provider_version: str
    capabilities: tuple[IntegrationCapability, ...]
    auth_kind: str = "none"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id is required")
        if not self.display_name.strip():
            raise ValueError("display_name is required")
        ids = [cap.capability_id for cap in self.capabilities]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate capability_id in manifest")

@dataclass(frozen=True)
class IntegrationProviderState:
    provider_id: str
    registered_at: str
    available: bool
    health_state: str
    last_checked_at: str
    last_error: Optional[str] = None

@dataclass(frozen=True)
class IntegrationRequest:
    request_id: str
    provider_id: str
    capability_id: str
    params: Mapping[str, Any]
    origin: str
    mission_id: Optional[str] = None
    task_id: Optional[str] = None

    @classmethod
    def create(
        cls,
        *,
        provider_id: str,
        capability_id: str,
        params: Optional[Mapping[str, Any]] = None,
        origin: str = "integration",
        mission_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> "IntegrationRequest":
        safe_params = dict(params or {})
        request_id = _stable_id(
            "irq_",
            provider_id,
            capability_id,
            safe_params,
            origin,
            mission_id,
            task_id,
        )
        return cls(
            request_id=request_id,
            provider_id=str(provider_id),
            capability_id=str(capability_id),
            params=safe_params,
            origin=str(origin),
            mission_id=mission_id,
            task_id=task_id,
        )

@dataclass(frozen=True)
class IntegrationResult:
    request_id: str
    provider_id: str
    capability_id: str
    status: str
    ok: bool
    receipt_id: str
    output: Any = None
    error: Optional[str] = None
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in INTEGRATION_RESULT_STATUSES:
            raise ValueError("invalid integration result status")

@runtime_checkable
class IntegrationProvider(Protocol):
    @property
    def manifest(self) -> IntegrationManifest:
        ...

    def execute(self, request: IntegrationRequest) -> Any:
        ...

    def health_snapshot(self) -> Mapping[str, Any]:
        ...

class IntegrationRegistry:
    """Canonical provider registry.

    SecurityPolicyEngine remains authorization authority.
    ActionReceiptService remains traceability authority.
    MissionEngine remains orchestration authority.
    """

    def __init__(
        self,
        *,
        security_engine: Any,
        receipt_service: ActionReceiptService,
    ):
        self.security_engine = security_engine
        self.receipt_service = receipt_service
        self._providers: dict[str, IntegrationProvider] = {}
        self._states: dict[str, IntegrationProviderState] = {}
        self._pending_receipts: dict[str, str] = {}

    def register_provider(
        self,
        provider: IntegrationProvider,
    ) -> IntegrationProviderState:
        if not isinstance(provider, IntegrationProvider):
            raise ProviderRegistrationError(
                "provider does not satisfy IntegrationProvider protocol"
            )
        manifest = provider.manifest
        provider_id = manifest.provider_id.strip()
        if not provider_id:
            raise ProviderRegistrationError("provider_id is required")
        if provider_id in self._providers:
            raise ProviderRegistrationError(
                "provider already registered: " + provider_id
            )
        self._providers[provider_id] = provider
        now = _utc_now()
        state = IntegrationProviderState(
            provider_id=provider_id,
            registered_at=now,
            available=True,
            health_state="registered",
            last_checked_at=now,
            last_error=None,
        )
        self._states[provider_id] = state
        return state

    def unregister_provider(self, provider_id: str) -> bool:
        provider_id = str(provider_id)
        existed = provider_id in self._providers
        self._providers.pop(provider_id, None)
        self._states.pop(provider_id, None)
        return existed

    def get_provider(
        self,
        provider_id: str,
    ) -> Optional[IntegrationProvider]:
        return self._providers.get(str(provider_id))

    def list_providers(self) -> tuple[IntegrationManifest, ...]:
        return tuple(
            self._providers[key].manifest
            for key in sorted(self._providers)
        )

    def resolve_capability(
        self,
        provider_id: str,
        capability_id: str,
    ) -> Optional[IntegrationCapability]:
        provider = self.get_provider(provider_id)
        if provider is None:
            return None
        for capability in provider.manifest.capabilities:
            if capability.capability_id == capability_id:
                return capability
        return None

    def build_integration_context(
        self,
        provider_id: str,
        capability_id: str,
    ) -> Optional[CapabilityContext]:
        provider = self.get_provider(provider_id)
        capability = self.resolve_capability(
            provider_id,
            capability_id,
        )
        state = self._states.get(str(provider_id))
        if provider is None or capability is None or state is None:
            return None
        return self.receipt_service.build_capability_context(
            capability_id=capability.capability_id,
            provider=provider.manifest.provider_id,
            available=state.available,
            permission_state=(
                "available" if state.available else "unavailable"
            ),
            risk_tier=capability.risk_tier,
            requires_confirmation=capability.requires_confirmation,
            side_effect_class=capability.side_effect_class,
            evidence_required=capability.evidence_required,
            health_state=state.health_state,
        )

    def health_snapshot(
        self,
        provider_id: Optional[str] = None,
    ) -> tuple[IntegrationProviderState, ...]:
        if provider_id is not None:
            state = self._states.get(str(provider_id))
            return (state,) if state is not None else ()
        return tuple(
            self._states[key]
            for key in sorted(self._states)
        )

    def _unknown_context(
        self,
        *,
        provider_id: str,
        capability_id: str,
    ) -> CapabilityContext:
        return self.receipt_service.build_capability_context(
            capability_id=capability_id or "unknown",
            provider=provider_id or "unknown",
            available=False,
            permission_state="unknown",
            risk_tier="unknown",
            requires_confirmation=True,
            side_effect_class="unknown",
            evidence_required=True,
            health_state="unknown",
        )

    def _begin_denied_receipt(
        self,
        request: IntegrationRequest,
        *,
        reason: str,
    ) -> IntegrationResult:
        context = self._unknown_context(
            provider_id=request.provider_id,
            capability_id=request.capability_id,
        )
        receipt = self.receipt_service.begin_receipt(
            action="integration." + reason,
            tool_name=request.provider_id or "integration.unknown",
            capability_context=context,
            origin=request.origin,
            params=request.params,
            mission_id=request.mission_id,
            task_id=request.task_id,
        )
        receipt = self.receipt_service.record_policy_decision(
            receipt.receipt_id,
            "DENY",
            user_confirmed=False,
        )
        return IntegrationResult(
            request_id=request.request_id,
            provider_id=request.provider_id,
            capability_id=request.capability_id,
            status="denied",
            ok=False,
            receipt_id=receipt.receipt_id,
            error=reason,
        )

    def _authorize(
        self,
        action: str,
        params: Mapping[str, Any],
        *,
        user_confirmed: bool,
    ) -> Any:
        # AURA_V122_INTEGRATION_PERMISSION_REGISTRY_BRIDGE_BEGIN
        # Existing v0.9.8 authority stays unchanged; tasks.* uses the v1.2.3 extension.
        _aura_action = str(action or "").strip()
        # AURA_W131_PC_CONTROL_PERMISSION_EXTENSION_BEGIN
        if _aura_action.startswith("pc."):
            try:
                from runtime.integration_permissions_pc_v131 import (
                    evaluate_integration_permission_pc_v131,
                )
                _aura_pc_decision = evaluate_integration_permission_pc_v131(
                    _aura_action,
                    params=params,
                    user_confirmed=user_confirmed,
                )
                return str(getattr(_aura_pc_decision, "decision", "DENY") or "DENY")
            except Exception:
                return "DENY"
        # AURA_W131_PC_CONTROL_PERMISSION_EXTENSION_END
        # AURA_V123_TASKS_PERMISSION_EXTENSION_BEGIN
        if _aura_action.startswith("tasks."):
            try:
                from runtime.integration_permissions_tasks_v123 import (
                    evaluate_integration_permission_tasks_v123,
                    get_integration_permission_rule_tasks_v123,
                )
                _aura_rule = get_integration_permission_rule_tasks_v123(_aura_action)
            except Exception:
                return "DENY"
            if _aura_rule is None:
                return "DENY"
            _aura_granted = getattr(self.security_engine, "granted_permissions", None)
            # AURA_V123_TASKS_READ_DEFAULT_GRANTS_PARITY_BEGIN
            # Missing granted_permissions intentionally delegates to the canonical
            # Tasks contract defaults: WEB_READ allowed, EXTERNAL_NETWORK absent.
            # AURA_V123_TASKS_READ_DEFAULT_GRANTS_PARITY_END
            try:
                _aura_decision = evaluate_integration_permission_tasks_v123(
                    _aura_action, granted_permissions=_aura_granted, user_confirmed=user_confirmed,
                )
                return str(getattr(_aura_decision, "decision", "DENY") or "DENY")
            except Exception:
                return "DENY"
        # AURA_V123_TASKS_PERMISSION_EXTENSION_END
        _aura_integration_prefixes = (
            "browser.", "calendar.", "contacts.", "email.", "files.", "notifications.",
        )
        if _aura_action.startswith(_aura_integration_prefixes):
            try:
                from runtime.integration_permissions_v098 import (
                    evaluate_integration_permission_v098,
                    get_integration_permission_rule_v098,
                )
                _aura_rule = get_integration_permission_rule_v098(_aura_action)
            except Exception:
                return "DENY"
            if _aura_rule is None:
                return "DENY"
            _aura_granted = getattr(self.security_engine, "granted_permissions", None)
            if _aura_granted is not None:
                try:
                    _aura_decision = evaluate_integration_permission_v098(
                        _aura_action, granted_permissions=_aura_granted, user_confirmed=user_confirmed,
                    )
                    return str(getattr(_aura_decision, "decision", "DENY") or "DENY")
                except Exception:
                    return "DENY"
        # AURA_V122_INTEGRATION_PERMISSION_REGISTRY_BRIDGE_END
        authorize = getattr(self.security_engine, "authorize", None)
        if not callable(authorize):
            return "DENY"
        try:
            return authorize(
                action,
                dict(params),
                user_confirmed=user_confirmed,
            )
        except TypeError:
            try:
                return authorize(action, dict(params))
            except Exception:
                return "DENY"
        except Exception:
            return "DENY"

    def _set_state(
        self,
        provider_id: str,
        *,
        available: bool,
        health_state: str,
        last_error: Optional[str],
    ) -> None:
        old = self._states.get(provider_id)
        self._states[provider_id] = IntegrationProviderState(
            provider_id=provider_id,
            registered_at=old.registered_at if old else _utc_now(),
            available=available,
            health_state=health_state,
            last_checked_at=_utc_now(),
            last_error=last_error,
        )

    def execute_integration(
        self,
        request: IntegrationRequest,
        *,
        user_confirmed: bool = False,
    ) -> IntegrationResult:
        provider = self.get_provider(request.provider_id)
        if provider is None:
            return self._begin_denied_receipt(
                request,
                reason="unknown_provider",
            )

        capability = self.resolve_capability(
            request.provider_id,
            request.capability_id,
        )
        if capability is None:
            return self._begin_denied_receipt(
                request,
                reason="unknown_capability",
            )

        context = self.build_integration_context(
            request.provider_id,
            request.capability_id,
        )
        if context is None or not context.available:
            return self._begin_denied_receipt(
                request,
                reason="provider_unavailable",
            )

        receipt = None
        pending_id = self._pending_receipts.get(request.request_id)
        if pending_id:
            candidate = self.receipt_service.get_receipt(pending_id)
            if candidate.status == "waiting_confirmation":
                receipt = candidate

        if receipt is None:
            receipt = self.receipt_service.begin_receipt(
                action=capability.action,
                tool_name=provider.manifest.provider_id,
                capability_context=context,
                origin=request.origin,
                params=request.params,
                mission_id=request.mission_id,
                task_id=request.task_id,
            )

        decision = self._authorize(
            capability.action,
            request.params,
            user_confirmed=user_confirmed,
        )
        receipt = self.receipt_service.record_policy_decision(
            receipt.receipt_id,
            decision,
            user_confirmed=user_confirmed,
        )

        if receipt.status == "waiting_confirmation":
            self._pending_receipts[request.request_id] = receipt.receipt_id
            return IntegrationResult(
                request_id=request.request_id,
                provider_id=request.provider_id,
                capability_id=request.capability_id,
                status="waiting_confirmation",
                ok=False,
                receipt_id=receipt.receipt_id,
            )

        self._pending_receipts.pop(request.request_id, None)

        if receipt.status == "denied":
            return IntegrationResult(
                request_id=request.request_id,
                provider_id=request.provider_id,
                capability_id=request.capability_id,
                status="denied",
                ok=False,
                receipt_id=receipt.receipt_id,
                error="authorization_denied",
            )

        try:
            self.receipt_service.mark_running(receipt.receipt_id)
            output = provider.execute(request)
        except Exception as exc:
            failed = self.receipt_service.fail_receipt(
                receipt.receipt_id,
                error=exc,
            )
            self._set_state(
                request.provider_id,
                available=True,
                health_state="degraded",
                last_error=type(exc).__name__,
            )
            return IntegrationResult(
                request_id=request.request_id,
                provider_id=request.provider_id,
                capability_id=request.capability_id,
                status="failed",
                ok=False,
                receipt_id=failed.receipt_id,
                error=type(exc).__name__,
                evidence_refs=tuple(failed.evidence_refs),
            )

        evidence_refs: Sequence[str] = ()
        if isinstance(output, Mapping):
            raw_refs = output.get("evidence_refs")
            if isinstance(raw_refs, (list, tuple, set)):
                evidence_refs = tuple(
                    str(x) for x in raw_refs if str(x)
                )

        completed = self.receipt_service.complete_receipt(
            receipt.receipt_id,
            result=output,
            evidence_refs=evidence_refs,
        )
        self._set_state(
            request.provider_id,
            available=True,
            health_state="healthy",
            last_error=None,
        )
        return IntegrationResult(
            request_id=request.request_id,
            provider_id=request.provider_id,
            capability_id=request.capability_id,
            status="succeeded",
            ok=True,
            receipt_id=completed.receipt_id,
            output=output,
            evidence_refs=tuple(completed.evidence_refs),
        )

class IntegrationMissionToolAdapter:
    """Callable translation boundary suitable for MissionEngine executors."""

    def __init__(
        self,
        *,
        registry: IntegrationRegistry,
        provider_id: str,
        capability_id: str,
        origin: str = "MissionEngine",
    ):
        self.registry = registry
        self.provider_id = provider_id
        self.capability_id = capability_id
        self.origin = origin

    def __call__(self, tool_call: Any) -> Any:
        request = IntegrationRequest.create(
            provider_id=self.provider_id,
            capability_id=self.capability_id,
            params=dict(getattr(tool_call, "params", {}) or {}),
            origin=self.origin,
        )
        result = self.registry.execute_integration(request)
        if not result.ok:
            raise IntegrationError(
                "integration execution failed: " + result.status
            )
        return result.output

__all__ = [
    "INTEGRATION_RESULT_STATUSES",
    "IntegrationError",
    "ProviderRegistrationError",
    "UnknownProviderError",
    "UnknownCapabilityError",
    "IntegrationCapability",
    "IntegrationManifest",
    "IntegrationProviderState",
    "IntegrationRequest",
    "IntegrationResult",
    "IntegrationProvider",
    "IntegrationRegistry",
    "IntegrationMissionToolAdapter",
]

# AURA V0.9.5 D2 R1 NOTIFICATIONS REGISTRY DESCRIPTOR
AURA_V095_NOTIFICATIONS_PROVIDER_DESCRIPTOR = {
    "id": "notifications.provider",
    "mode": "BRIDGE_EXISTING_P081_P083",
    "capabilities": (
        "notifications.list",
        "notifications.read",
        "notifications.create",
        "notifications.mark_read",
        "notifications.dismiss",
        "notifications.clear",
    ),
    "legacy": {
        "history_ui": "P0.8.1 Activity Center",
        "presentation": "P0.8.3 AuraProactiveNotifications",
        "duplicate_history_ui": False,
        "duplicate_popup_layer": False,
    },
    "external_delivery": False,
    "network_side_effects": False,
    "windows_notifications": False,
    "auto_action": False,
}

# AURA_V096_BROWSER_PROVIDER_DESCRIPTOR_BEGIN
AURA_V096_BROWSER_PROVIDER_DESCRIPTOR = {
    "provider_id": "browser.provider",
    "display_name": "Browser / Web Workflows",
    "provider_version": "0.9.6",
    "strategy": "MINIMAL_WIRING_AROUND_CERTIFIED_AUTHORITIES",
    "capabilities": (
        "browser.open",
        "browser.navigate",
        "browser.read",
        "browser.extract",
        "browser.search",
        "browser.click",
        "browser.fill",
        "browser.submit",
        "browser.download",
        "browser.workflow",
    ),
    "state_changing_executor": "DISABLED",
    "evidence_required": True,
    "external_content_trust": "UNTRUSTED_BY_DEFAULT",
}
# AURA_V096_BROWSER_PROVIDER_DESCRIPTOR_END
