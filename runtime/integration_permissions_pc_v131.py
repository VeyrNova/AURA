from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

PC_ALLOWED_ACTIONS = frozenset({
    "pc.discover_windows",
    "pc.discover_processes",
    "pc.get_foreground_window",
    "pc.focus_window",
    "pc.minimize_window",
    "pc.maximize_window",
    "pc.restore_window_state",
})

PC_DENIED_ACTIONS = frozenset({
    "pc.close_window",
    "pc.terminate_process",
})


@dataclass(frozen=True)
class PcIntegrationPermissionDecision:
    decision: str
    action: str
    reason: str


def evaluate_integration_permission_pc_v131(
    action: str,
    *,
    params: Mapping[str, Any] | None = None,
    user_confirmed: bool = False,
) -> PcIntegrationPermissionDecision:
    action = str(action or "").strip().casefold()
    params = dict(params or {})

    if action in PC_DENIED_ACTIONS:
        return PcIntegrationPermissionDecision(
            "DENY", action, "destructive_pc_action_not_bound",
        )

    if action not in PC_ALLOWED_ACTIONS:
        return PcIntegrationPermissionDecision(
            "DENY", action, "pc_action_outside_w131_registry_perimeter",
        )

    denied_keys = {
        "command", "cmd", "shell", "powershell", "script",
        "argv", "arguments", "executable", "exe_path",
    }
    if any(str(k).strip().casefold() in denied_keys for k in params):
        return PcIntegrationPermissionDecision(
            "DENY", action, "raw_execution_material_denied",
        )

    return PcIntegrationPermissionDecision(
        "ALLOW", action, "w131_typed_pc_capability",
    )
