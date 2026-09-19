from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Optional
from uuid import uuid4

from integrations.registry import IntegrationRequest
from runtime.integration_permissions_v098 import (
    ALLOW,
    DENY,
    REQUIRE_CONFIRMATION,
    evaluate_integration_permission_v098,
)
from security.permissions import Permission

from .registry import SkillCapabilityRegistryV100


class SecureSkillRuntimeError(RuntimeError):
    pass


class UnknownSkillRuntimeError(SecureSkillRuntimeError):
    pass


class UnknownSkillBindingError(SecureSkillRuntimeError):
    pass


class SkillPermissionDeniedError(SecureSkillRuntimeError):
    pass


class SkillRuntimeContractError(SecureSkillRuntimeError):
    pass


@dataclass(frozen=True)
class SkillRuntimePreflightV101:
    skill_id: str
    provider_id: str
    capability_id: str
    decision: str
    reason: str
    permission: Optional[Permission]
    requires_confirmation: bool


class SecureSkillRuntimeV101:
    """Secure execution bridge for v1.0.1 Skills.

    This class does not execute arbitrary Python, spawn processes, open its own
    network stack, or implement a second receipt/security engine. It resolves a
    v1.0.0 Skill binding, applies the v0.9.8 permission contract as a fail-closed
    preflight, then delegates the actual request to the existing
    IntegrationRegistry.execute_integration authority.
    """

    _RESERVED_PARAM_KEYS = frozenset({
        "user_confirmed",
    })

    def __init__(
        self,
        *,
        skill_registry: SkillCapabilityRegistryV100,
        integration_registry: Any,
        granted_permissions: Optional[Iterable[Permission]] = None,
    ):
        if not isinstance(skill_registry, SkillCapabilityRegistryV100):
            raise TypeError("SkillCapabilityRegistryV100 required")
        if integration_registry is None or not callable(
            getattr(integration_registry, "execute_integration", None)
        ):
            raise TypeError(
                "integration_registry with execute_integration(request, user_confirmed=...) required"
            )

        self._skill_registry = skill_registry
        self._integration_registry = integration_registry
        self._granted_permissions = (
            None
            if granted_permissions is None
            else frozenset(granted_permissions)
        )

    @property
    def granted_permissions(self) -> Optional[frozenset[Permission]]:
        return self._granted_permissions

    def preflight(
        self,
        *,
        skill_id: str,
        provider_id: str,
        capability_id: str,
        user_confirmed: bool = False,
    ) -> SkillRuntimePreflightV101:
        skill_id = str(skill_id or "").strip()
        provider_id = str(provider_id or "").strip()
        capability_id = str(capability_id or "").strip()

        if self._skill_registry.get_manifest(skill_id) is None:
            raise UnknownSkillRuntimeError(skill_id)

        binding = self._skill_registry.resolve_binding(
            skill_id,
            provider_id,
            capability_id,
        )
        if binding is None:
            raise UnknownSkillBindingError(
                skill_id + ":" + provider_id + ":" + capability_id
            )

        decision = evaluate_integration_permission_v098(
            capability_id,
            granted_permissions=self._granted_permissions,
            user_confirmed=bool(user_confirmed),
        )

        if decision.provider_id != provider_id:
            raise SkillRuntimeContractError(
                "permission_provider_mismatch:"
                + provider_id
                + ":"
                + str(decision.provider_id)
            )

        return SkillRuntimePreflightV101(
            skill_id=skill_id,
            provider_id=provider_id,
            capability_id=capability_id,
            decision=str(decision.decision),
            reason=str(decision.reason),
            permission=decision.permission,
            requires_confirmation=bool(
                decision.requires_confirmation
            ),
        )

    def execute(
        self,
        *,
        skill_id: str,
        provider_id: str,
        capability_id: str,
        params: Optional[Mapping[str, Any]] = None,
        mission_id: Optional[str] = None,
        task_id: Optional[str] = None,
        user_confirmed: bool = False,
        request_id: Optional[str] = None,
    ) -> Any:
        safe_params = dict(params or {})
        reserved = sorted(
            key
            for key in safe_params
            if str(key) in self._RESERVED_PARAM_KEYS
        )
        if reserved:
            raise SkillRuntimeContractError(
                "reserved_params:" + ",".join(reserved)
            )

        preflight = self.preflight(
            skill_id=skill_id,
            provider_id=provider_id,
            capability_id=capability_id,
            user_confirmed=bool(user_confirmed),
        )

        if preflight.decision == DENY:
            raise SkillPermissionDeniedError(
                preflight.capability_id + ":" + preflight.reason
            )

        if preflight.decision not in {
            ALLOW,
            REQUIRE_CONFIRMATION,
        }:
            raise SkillRuntimeContractError(
                "unknown_permission_decision:" + preflight.decision
            )

        rid = str(request_id or "").strip()
        if not rid:
            rid = "skill-" + uuid4().hex

        request = IntegrationRequest(
            request_id=rid,
            provider_id=preflight.provider_id,
            capability_id=preflight.capability_id,
            params=MappingProxyType(safe_params),
            origin="skill.runtime.v101:" + preflight.skill_id,
            mission_id=mission_id,
            task_id=task_id,
        )

        # Critical invariant: never promote confirmation internally.
        # The caller-provided boolean is forwarded byte-for-byte as bool.
        return self._integration_registry.execute_integration(
            request,
            user_confirmed=bool(user_confirmed),
        )


__all__ = [
    "SecureSkillRuntimeError",
    "UnknownSkillRuntimeError",
    "UnknownSkillBindingError",
    "SkillPermissionDeniedError",
    "SkillRuntimeContractError",
    "SkillRuntimePreflightV101",
    "SecureSkillRuntimeV101",
]
