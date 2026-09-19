from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from security.permissions import ACTION_POLICIES
from security.risk import RiskLevel


class PolicyDecisionV2(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"


@dataclass(frozen=True)
class NormalizedSecurityDecisionV2:
    action: str
    decision: PolicyDecisionV2
    risk_level: str
    reason: str
    requires_confirmation: bool
    policy_rule: str


def normalize_legacy_decision(action: str, legacy: Any) -> NormalizedSecurityDecisionV2:
    allowed = bool(getattr(legacy, "allowed", False))
    requires_confirmation = bool(
        getattr(
            legacy,
            "requires_confirmation",
            getattr(legacy, "confirmation_required", getattr(legacy, "needs_confirmation", False)),
        )
    )

    if allowed and requires_confirmation:
        decision = PolicyDecisionV2.REQUIRE_CONFIRMATION
    elif allowed:
        decision = PolicyDecisionV2.ALLOW
    else:
        decision = PolicyDecisionV2.DENY

    risk = getattr(legacy, "risk_level", getattr(legacy, "risk", "UNKNOWN"))
    if hasattr(risk, "name"):
        risk_text = str(risk.name)
    elif hasattr(risk, "value"):
        risk_text = str(risk.value)
    else:
        risk_text = str(risk)

    reason = str(
        getattr(legacy, "reason", getattr(legacy, "message", getattr(legacy, "detail", "legacy_policy_decision")))
    )

    return NormalizedSecurityDecisionV2(
        action=str(action or ""),
        decision=decision,
        risk_level=risk_text,
        reason=reason,
        requires_confirmation=requires_confirmation,
        policy_rule="legacy.authorize",
    )


def build_fail_closed_decision(SecurityDecisionType: type, action: str, reason: str):
    return SecurityDecisionType(
            allowed=False,
            action=str(action or ''),
            risk=RiskLevel.CRITICAL,
            reason=reason,
            confirmation_required=False
    )


class SecurityPolicyEvaluatorV2:
    # Fail-closed adapter around the certified legacy policy evaluator.
    @staticmethod
    def authorize(
        legacy_authorize: Callable[[str, dict[str, Any]], Any],
        SecurityDecisionType: type,
        action: str,
        params: dict[str, Any] | None,
    ):
        normalized_action = str(action or "").strip().upper()
        safe_params = params if isinstance(params, dict) else {}

        if not normalized_action or normalized_action not in ACTION_POLICIES:
            return build_fail_closed_decision(
                SecurityDecisionType,
                normalized_action,
                "security_policy_v2:unknown_action_denied",
            )

        try:
            decision = legacy_authorize(normalized_action, safe_params)
        except Exception as exc:
            return build_fail_closed_decision(
                SecurityDecisionType,
                normalized_action,
                "security_policy_v2:evaluator_exception_denied:" + type(exc).__name__,
            )

        if decision is None:
            return build_fail_closed_decision(
                SecurityDecisionType,
                normalized_action,
                "security_policy_v2:null_decision_denied",
            )

        return decision
