from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import FrozenSet, Iterable, Mapping, Optional

from security.permissions import (
    ActionPolicy,
    DEFAULT_GRANTED_PERMISSIONS,
    Permission,
    RiskLevel,
)


ALLOW = "ALLOW"
DENY = "DENY"
REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"


@dataclass(frozen=True)
class IntegrationPermissionRuleV098:
    capability_id: str
    provider_id: str
    permission: Permission
    risk: RiskLevel
    confirmation_required: bool
    effect: str
    mode: str = "allow"

    @property
    def allowed(self) -> bool:
        return self.mode == "allow"


@dataclass(frozen=True)
class IntegrationPermissionDecisionV098:
    capability_id: str
    decision: str
    permission: Optional[Permission]
    risk: Optional[RiskLevel]
    requires_confirmation: bool
    reason: str
    provider_id: Optional[str]


def _r(
    capability_id: str,
    provider_id: str,
    permission: Permission,
    risk: RiskLevel,
    confirmation_required: bool,
    effect: str,
    mode: str = "allow",
) -> IntegrationPermissionRuleV098:
    return IntegrationPermissionRuleV098(
        capability_id=capability_id,
        provider_id=provider_id,
        permission=permission,
        risk=risk,
        confirmation_required=bool(confirmation_required),
        effect=effect,
        mode=mode,
    )


_RULES = {
    # Browser — the ten certified v0.9.6 routes plus explicit fail-closed exclusions.
    "browser.open": _r("browser.open", "browser.provider", Permission.WEB_READ, RiskLevel.LOW, False, "read_only"),
    "browser.navigate": _r("browser.navigate", "browser.provider", Permission.WEB_READ, RiskLevel.LOW, False, "read_only"),
    "browser.read": _r("browser.read", "browser.provider", Permission.WEB_READ, RiskLevel.LOW, False, "read_only"),
    "browser.extract": _r("browser.extract", "browser.provider", Permission.WEB_READ, RiskLevel.LOW, False, "read_only"),
    "browser.search": _r("browser.search", "browser.provider", Permission.WEB_READ, RiskLevel.LOW, False, "read_only"),
    "browser.workflow": _r("browser.workflow", "browser.provider", Permission.WEB_READ, RiskLevel.LOW, False, "orchestrated"),
    "browser.click": _r("browser.click", "browser.provider", Permission.BROWSER_MUTATE, RiskLevel.MEDIUM, True, "state_change"),
    "browser.fill": _r("browser.fill", "browser.provider", Permission.BROWSER_MUTATE, RiskLevel.MEDIUM, True, "state_change"),
    "browser.submit": _r("browser.submit", "browser.provider", Permission.BROWSER_MUTATE, RiskLevel.MEDIUM, True, "state_change"),
    "browser.download": _r("browser.download", "browser.provider", Permission.BROWSER_DOWNLOAD, RiskLevel.MEDIUM, True, "local_side_effect"),
    "browser.antibot_bypass": _r("browser.antibot_bypass", "browser.provider", Permission.SYSTEM_CHANGE, RiskLevel.CRITICAL, False, "denied", "deny"),
    "browser.captcha_bypass": _r("browser.captcha_bypass", "browser.provider", Permission.SYSTEM_CHANGE, RiskLevel.CRITICAL, False, "denied", "deny"),
    "browser.credentials": _r("browser.credentials", "browser.provider", Permission.SECRET_ACCESS, RiskLevel.CRITICAL, False, "denied", "deny"),
    "browser.pay": _r("browser.pay", "browser.provider", Permission.EXTERNAL_NETWORK, RiskLevel.CRITICAL, False, "denied", "deny"),
    "browser.purchase": _r("browser.purchase", "browser.provider", Permission.EXTERNAL_NETWORK, RiskLevel.CRITICAL, False, "denied", "deny"),
    "browser.transfer": _r("browser.transfer", "browser.provider", Permission.EXTERNAL_NETWORK, RiskLevel.CRITICAL, False, "denied", "deny"),

    # Calendar.
    "calendar.free_busy": _r("calendar.free_busy", "calendar.provider", Permission.WEB_READ, RiskLevel.LOW, False, "read_only"),
    "calendar.list": _r("calendar.list", "calendar.provider", Permission.WEB_READ, RiskLevel.LOW, False, "read_only"),
    "calendar.read_event": _r("calendar.read_event", "calendar.provider", Permission.WEB_READ, RiskLevel.LOW, False, "read_only"),
    "calendar.search_events": _r("calendar.search_events", "calendar.provider", Permission.WEB_READ, RiskLevel.LOW, False, "read_only"),
    "calendar.create_event": _r("calendar.create_event", "calendar.provider", Permission.EXTERNAL_NETWORK, RiskLevel.MEDIUM, True, "state_change"),
    "calendar.update_event": _r("calendar.update_event", "calendar.provider", Permission.EXTERNAL_NETWORK, RiskLevel.MEDIUM, True, "state_change"),
    "calendar.respond_invitation": _r("calendar.respond_invitation", "calendar.provider", Permission.EXTERNAL_NETWORK, RiskLevel.MEDIUM, True, "state_change"),
    "calendar.delete_event": _r("calendar.delete_event", "calendar.provider", Permission.EXTERNAL_NETWORK, RiskLevel.HIGH, True, "state_change"),

    # Contacts.
    "contacts.search": _r("contacts.search", "contacts.provider", Permission.READ_LOCAL_DATA, RiskLevel.LOW, False, "read_only"),
    "contacts.read": _r("contacts.read", "contacts.provider", Permission.READ_LOCAL_DATA, RiskLevel.LOW, False, "read_only"),
    "contacts.create": _r("contacts.create", "contacts.provider", Permission.WRITE_LOCAL_DATA, RiskLevel.MEDIUM, True, "state_change"),
    "contacts.update": _r("contacts.update", "contacts.provider", Permission.WRITE_LOCAL_DATA, RiskLevel.MEDIUM, True, "state_change"),
    "contacts.delete": _r("contacts.delete", "contacts.provider", Permission.DELETE_LOCAL_RECORDS, RiskLevel.HIGH, True, "state_change"),

    # Email.
    "email.search": _r("email.search", "email.provider", Permission.WEB_READ, RiskLevel.LOW, False, "read_only"),
    "email.read": _r("email.read", "email.provider", Permission.WEB_READ, RiskLevel.LOW, False, "read_only"),
    "email.read_thread": _r("email.read_thread", "email.provider", Permission.WEB_READ, RiskLevel.LOW, False, "read_only"),
    "email.list_attachments": _r("email.list_attachments", "email.provider", Permission.WEB_READ, RiskLevel.LOW, False, "read_only"),
    "email.create_draft": _r("email.create_draft", "email.provider", Permission.EXTERNAL_NETWORK, RiskLevel.MEDIUM, False, "state_change"),
    "email.send": _r("email.send", "email.provider", Permission.EXTERNAL_NETWORK, RiskLevel.HIGH, True, "external_side_effect"),
    "email.reply": _r("email.reply", "email.provider", Permission.EXTERNAL_NETWORK, RiskLevel.HIGH, True, "external_side_effect"),
    "email.forward": _r("email.forward", "email.provider", Permission.EXTERNAL_NETWORK, RiskLevel.HIGH, True, "external_side_effect"),
    "email.archive": _r("email.archive", "email.provider", Permission.EXTERNAL_NETWORK, RiskLevel.MEDIUM, True, "state_change"),
    "email.label": _r("email.label", "email.provider", Permission.EXTERNAL_NETWORK, RiskLevel.MEDIUM, True, "state_change"),
    "email.trash": _r("email.trash", "email.provider", Permission.EXTERNAL_NETWORK, RiskLevel.HIGH, True, "state_change"),

    # Files.
    "files.list": _r("files.list", "files.provider", Permission.AUTHORIZED_FOLDER_ACCESS, RiskLevel.LOW, False, "read_only"),
    "files.search": _r("files.search", "files.provider", Permission.AUTHORIZED_FOLDER_ACCESS, RiskLevel.LOW, False, "read_only"),
    "files.read": _r("files.read", "files.provider", Permission.AUTHORIZED_FILE_READ, RiskLevel.LOW, False, "read_only"),
    "files.create": _r("files.create", "files.provider", Permission.WRITE_LOCAL_DATA, RiskLevel.MEDIUM, True, "local_side_effect"),
    "files.update": _r("files.update", "files.provider", Permission.WRITE_LOCAL_DATA, RiskLevel.MEDIUM, True, "local_side_effect"),
    "files.move": _r("files.move", "files.provider", Permission.WRITE_LOCAL_DATA, RiskLevel.MEDIUM, True, "local_side_effect"),
    "files.delete": _r("files.delete", "files.provider", Permission.FILESYSTEM_DELETE, RiskLevel.HIGH, True, "local_side_effect"),

    # Notifications.
    "notifications.list": _r("notifications.list", "notifications.provider", Permission.READ_LOCAL_DATA, RiskLevel.SAFE, False, "read_only"),
    "notifications.read": _r("notifications.read", "notifications.provider", Permission.READ_LOCAL_DATA, RiskLevel.SAFE, False, "read_only"),
    "notifications.create": _r("notifications.create", "notifications.provider", Permission.WRITE_LOCAL_DATA, RiskLevel.LOW, False, "state_change"),
    "notifications.mark_read": _r("notifications.mark_read", "notifications.provider", Permission.WRITE_LOCAL_DATA, RiskLevel.LOW, False, "state_change"),
    "notifications.dismiss": _r("notifications.dismiss", "notifications.provider", Permission.WRITE_LOCAL_DATA, RiskLevel.LOW, False, "state_change"),
    "notifications.clear": _r("notifications.clear", "notifications.provider", Permission.DELETE_LOCAL_RECORDS, RiskLevel.MEDIUM, True, "state_change"),
}


INTEGRATION_PERMISSION_RULES_V098: Mapping[str, IntegrationPermissionRuleV098] = MappingProxyType(_RULES)

CANONICAL_PROVIDER_CAPABILITIES_V098: Mapping[str, FrozenSet[str]] = MappingProxyType({
    provider_id: frozenset(
        capability_id
        for capability_id, rule in _RULES.items()
        if rule.provider_id == provider_id
    )
    for provider_id in (
        "browser.provider",
        "calendar.provider",
        "contacts.provider",
        "email.provider",
        "files.provider",
        "notifications.provider",
    )
})

DENIED_BROWSER_CAPABILITIES_V098: FrozenSet[str] = frozenset({
    "browser.antibot_bypass",
    "browser.captcha_bypass",
    "browser.credentials",
    "browser.pay",
    "browser.purchase",
    "browser.transfer",
})


def get_integration_permission_rule_v098(
    capability_id: str,
) -> Optional[IntegrationPermissionRuleV098]:
    return INTEGRATION_PERMISSION_RULES_V098.get(str(capability_id or "").strip())


def action_policy_for_integration_capability_v098(
    capability_id: str,
) -> Optional[ActionPolicy]:
    rule = get_integration_permission_rule_v098(capability_id)
    if rule is None or not rule.allowed:
        return None
    return ActionPolicy(
        risk=rule.risk,
        permission=rule.permission,
        confirmation_required=rule.confirmation_required,
    )


def evaluate_integration_permission_v098(
    capability_id: str,
    *,
    granted_permissions: Optional[Iterable[Permission]] = None,
    user_confirmed: bool = False,
) -> IntegrationPermissionDecisionV098:
    rule = get_integration_permission_rule_v098(capability_id)
    if rule is None:
        return IntegrationPermissionDecisionV098(
            capability_id=str(capability_id or ""),
            decision=DENY,
            permission=None,
            risk=None,
            requires_confirmation=False,
            reason="unknown_integration_capability",
            provider_id=None,
        )

    if not rule.allowed:
        return IntegrationPermissionDecisionV098(
            capability_id=rule.capability_id,
            decision=DENY,
            permission=rule.permission,
            risk=rule.risk,
            requires_confirmation=False,
            reason="capability_explicitly_denied",
            provider_id=rule.provider_id,
        )

    granted = (
        frozenset(DEFAULT_GRANTED_PERMISSIONS)
        if granted_permissions is None
        else frozenset(granted_permissions)
    )

    if rule.permission not in granted:
        return IntegrationPermissionDecisionV098(
            capability_id=rule.capability_id,
            decision=DENY,
            permission=rule.permission,
            risk=rule.risk,
            requires_confirmation=rule.confirmation_required,
            reason="permission_not_granted",
            provider_id=rule.provider_id,
        )

    if rule.confirmation_required and not bool(user_confirmed):
        return IntegrationPermissionDecisionV098(
            capability_id=rule.capability_id,
            decision=REQUIRE_CONFIRMATION,
            permission=rule.permission,
            risk=rule.risk,
            requires_confirmation=True,
            reason="explicit_confirmation_required",
            provider_id=rule.provider_id,
        )

    return IntegrationPermissionDecisionV098(
        capability_id=rule.capability_id,
        decision=ALLOW,
        permission=rule.permission,
        risk=rule.risk,
        requires_confirmation=rule.confirmation_required,
        reason="integration_permission_contract_allow",
        provider_id=rule.provider_id,
    )


def validate_integration_permission_contract_v098() -> tuple[str, ...]:
    errors = []
    for capability_id, rule in INTEGRATION_PERMISSION_RULES_V098.items():
        if capability_id != rule.capability_id:
            errors.append("capability_key_mismatch:" + capability_id)
        if not capability_id.startswith(rule.provider_id.split(".", 1)[0] + "."):
            errors.append("provider_prefix_mismatch:" + capability_id)
        if rule.mode not in {"allow", "deny"}:
            errors.append("invalid_mode:" + capability_id)
        if not isinstance(rule.permission, Permission):
            errors.append("invalid_permission:" + capability_id)
        if not isinstance(rule.risk, RiskLevel):
            errors.append("invalid_risk:" + capability_id)
        if rule.mode == "deny" and rule.confirmation_required:
            errors.append("denied_capability_must_not_wait_confirmation:" + capability_id)
    return tuple(errors)


__all__ = [
    "ALLOW",
    "DENY",
    "REQUIRE_CONFIRMATION",
    "IntegrationPermissionRuleV098",
    "IntegrationPermissionDecisionV098",
    "INTEGRATION_PERMISSION_RULES_V098",
    "CANONICAL_PROVIDER_CAPABILITIES_V098",
    "DENIED_BROWSER_CAPABILITIES_V098",
    "get_integration_permission_rule_v098",
    "action_policy_for_integration_capability_v098",
    "evaluate_integration_permission_v098",
    "validate_integration_permission_contract_v098",
]
