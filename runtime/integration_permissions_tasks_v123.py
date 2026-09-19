from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Optional

from security.permissions import DEFAULT_GRANTED_PERMISSIONS, Permission, RiskLevel

ALLOW = "ALLOW"
DENY = "DENY"
REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"


@dataclass(frozen=True)
class TasksPermissionRuleV123:
    capability_id: str
    provider_id: str
    permission: Permission
    risk: RiskLevel
    confirmation_required: bool
    effect: str


@dataclass(frozen=True)
class TasksPermissionDecisionV123:
    capability_id: str
    decision: str
    permission: Optional[Permission]
    risk: Optional[RiskLevel]
    requires_confirmation: bool
    reason: str
    provider_id: Optional[str]


def _r(capability_id, permission, risk, confirmation, effect):
    return TasksPermissionRuleV123(
        capability_id=capability_id,
        provider_id="tasks.provider",
        permission=permission,
        risk=risk,
        confirmation_required=confirmation,
        effect=effect,
    )


TASKS_PERMISSION_RULES_V123 = MappingProxyType(
    {
        "tasks.tasklists": _r("tasks.tasklists", Permission.WEB_READ, RiskLevel.LOW, False, "read_only"),
        "tasks.list": _r("tasks.list", Permission.WEB_READ, RiskLevel.LOW, False, "read_only"),
        "tasks.read": _r("tasks.read", Permission.WEB_READ, RiskLevel.LOW, False, "read_only"),
        "tasks.create": _r("tasks.create", Permission.EXTERNAL_NETWORK, RiskLevel.MEDIUM, True, "state_change"),
        "tasks.update": _r("tasks.update", Permission.EXTERNAL_NETWORK, RiskLevel.MEDIUM, True, "state_change"),
        "tasks.complete": _r("tasks.complete", Permission.EXTERNAL_NETWORK, RiskLevel.MEDIUM, True, "state_change"),
        "tasks.delete": _r("tasks.delete", Permission.EXTERNAL_NETWORK, RiskLevel.HIGH, True, "state_change"),
    }
)


def get_integration_permission_rule_tasks_v123(capability_id):
    return TASKS_PERMISSION_RULES_V123.get(str(capability_id or "").strip())


def evaluate_integration_permission_tasks_v123(
    capability_id,
    *,
    granted_permissions: Optional[Iterable[Permission]] = None,
    user_confirmed=False,
):
    rule = get_integration_permission_rule_tasks_v123(capability_id)
    if rule is None:
        return TasksPermissionDecisionV123(
            str(capability_id or ""), DENY, None, None, False,
            "unknown_tasks_capability", None,
        )
    granted = (
        frozenset(DEFAULT_GRANTED_PERMISSIONS)
        if granted_permissions is None
        else frozenset(granted_permissions)
    )
    if rule.permission not in granted:
        return TasksPermissionDecisionV123(
            rule.capability_id, DENY, rule.permission, rule.risk,
            rule.confirmation_required, "permission_not_granted", rule.provider_id,
        )
    if rule.confirmation_required and not bool(user_confirmed):
        return TasksPermissionDecisionV123(
            rule.capability_id, REQUIRE_CONFIRMATION, rule.permission, rule.risk,
            True, "explicit_confirmation_required", rule.provider_id,
        )
    return TasksPermissionDecisionV123(
        rule.capability_id, ALLOW, rule.permission, rule.risk,
        rule.confirmation_required, "tasks_permission_contract_allow", rule.provider_id,
    )


__all__ = [
    "ALLOW", "DENY", "REQUIRE_CONFIRMATION",
    "TasksPermissionRuleV123", "TasksPermissionDecisionV123",
    "TASKS_PERMISSION_RULES_V123",
    "get_integration_permission_rule_tasks_v123",
    "evaluate_integration_permission_tasks_v123",
]
