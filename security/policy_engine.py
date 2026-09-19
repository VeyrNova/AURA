"""Deterministic SecurityPolicyEngine for AURA v0.5."""
from dataclasses import dataclass
from typing import Iterable

from security.audit import SecurityAuditLogger
from security.permissions import (
    ACTION_POLICIES,
    DEFAULT_GRANTED_PERMISSIONS,
    Permission,
)
from security.risk import RiskLevel


@dataclass(frozen=True)
class SecurityDecision:
    allowed: bool
    action: str
    risk: RiskLevel
    reason: str
    confirmation_required: bool = False


class SecurityPolicyEngine:
    """Authorize structured actions independently from the LLM.

    Fail-closed rules:
    - unknown actions are denied;
    - missing permissions are denied;
    - CRITICAL actions are always denied in v0.4.1;
    - HIGH actions require explicit confirmation and an enabled permission.
    """

    def __init__(self, db=None, granted_permissions: Iterable[Permission] | None = None):
        self.granted_permissions = frozenset(
            granted_permissions if granted_permissions is not None else DEFAULT_GRANTED_PERMISSIONS
        )
        self.audit = SecurityAuditLogger(db)

    def authorize(
        self,
        action: str,
        params: dict | None = None,
        *,
        user_confirmed: bool = False,
    ) -> SecurityDecision:
        del params  # Reserved for parameter-aware policies in later versions.
        normalized_action = (action or "").strip().upper()
        policy = ACTION_POLICIES.get(normalized_action)

        if policy is None:
            decision = SecurityDecision(
                allowed=False,
                action=normalized_action or "<EMPTY>",
                risk=RiskLevel.CRITICAL,
                reason="Action inconnue : refus par defaut (fail closed).",
            )
            self._audit(decision)
            return decision

        if policy.risk is RiskLevel.CRITICAL:
            decision = SecurityDecision(
                allowed=False,
                action=normalized_action,
                risk=policy.risk,
                reason="Action critique bloquee par la politique AURA v0.5.",
                confirmation_required=True,
            )
            self._audit(decision)
            return decision

        if policy.permission not in self.granted_permissions:
            decision = SecurityDecision(
                allowed=False,
                action=normalized_action,
                risk=policy.risk,
                reason=f"Permission absente : {policy.permission.value}.",
                confirmation_required=policy.confirmation_required,
            )
            self._audit(decision)
            return decision

        if policy.confirmation_required and not user_confirmed:
            decision = SecurityDecision(
                allowed=False,
                action=normalized_action,
                risk=policy.risk,
                reason="Confirmation utilisateur explicite requise.",
                confirmation_required=True,
            )
            self._audit(decision)
            return decision

        decision = SecurityDecision(
            allowed=True,
            action=normalized_action,
            risk=policy.risk,
            reason="Action autorisee par la politique locale.",
            confirmation_required=policy.confirmation_required,
        )
        self._audit(decision)
        return decision

    def _audit(self, decision: SecurityDecision) -> None:
        self.audit.record(
            action=decision.action,
            risk=decision.risk,
            allowed=decision.allowed,
            reason=decision.reason,
        )

# AURA v0.8.6.6 SecurityPolicyEngine v2 compatibility facade
_SecurityPolicyEngineV1 = SecurityPolicyEngine


class SecurityPolicyEngine(_SecurityPolicyEngineV1):
    # Compatibility facade preserving the public v1 constructor/API.
    SECURITY_POLICY_VERSION = "2"

    # AURA v0.8.7 - router user_confirmed compatibility
    def authorize(self, action, params, user_confirmed=False):
        from security.policy_engine_v2 import SecurityPolicyEvaluatorV2

        safe_params = dict(params or {})
        if user_confirmed:
            safe_params.setdefault("user_confirmed", True)

        return SecurityPolicyEvaluatorV2.authorize(
            super().authorize,
            SecurityDecision,
            action,
            safe_params,
        )

