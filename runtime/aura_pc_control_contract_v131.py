from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping

SCHEMA = "aura.pc-control.contract.v131"
REQUEST_SCHEMA = "aura.pc-control.request.v131"
PLAN_SCHEMA = "aura.pc-control.plan.v131"

READ_ONLY_ACTIONS = frozenset({
    "DISCOVER_WINDOWS",
    "DISCOVER_PROCESSES",
    "GET_FOREGROUND_WINDOW",
})

WINDOW_ACTIONS = frozenset({
    "FOCUS_WINDOW",
    "MINIMIZE_WINDOW",
    "MAXIMIZE_WINDOW",
    "CLOSE_WINDOW",
})

PROCESS_ACTIONS = frozenset({
    "TERMINATE_PROCESS",
})

DELEGATED_ACTIONS = frozenset({
    "OPEN_SAFE_APP",
})

ALL_ACTIONS = (
    READ_ONLY_ACTIONS
    | WINDOW_ACTIONS
    | PROCESS_ACTIONS
    | DELEGATED_ACTIONS
)

DENIED_RAW_EXECUTION_KEYS = frozenset({
    "command",
    "cmd",
    "shell",
    "powershell",
    "script",
    "argv",
    "arguments",
    "executable",
    "exe_path",
})


class PcControlContractError(ValueError):
    pass


@dataclass(frozen=True)
class ActionSpec:
    action: str
    risk_tier: str
    requires_confirmation: bool
    mutating: bool
    reversible: bool
    owner: str
    executor_state: str
    description: str


ACTION_SPECS: dict[str, ActionSpec] = {
    "DISCOVER_WINDOWS": ActionSpec(
        "DISCOVER_WINDOWS", "low", False, False, False,
        "pc-control.v131", "unbound",
        "Read-only discovery of visible Windows desktop windows.",
    ),
    "DISCOVER_PROCESSES": ActionSpec(
        "DISCOVER_PROCESSES", "low", False, False, False,
        "pc-control.v131", "unbound",
        "Read-only discovery of running processes.",
    ),
    "GET_FOREGROUND_WINDOW": ActionSpec(
        "GET_FOREGROUND_WINDOW", "low", False, False, False,
        "pc-control.v131", "unbound",
        "Read-only discovery of the current foreground window.",
    ),
    "OPEN_SAFE_APP": ActionSpec(
        "OPEN_SAFE_APP", "low", False, True, True,
        "route_contract.system-safe-app", "delegated",
        "Delegate to AURA's existing fixed safe-app launcher.",
    ),
    "FOCUS_WINDOW": ActionSpec(
        "FOCUS_WINDOW", "low", False, True, True,
        "pc-control.v131", "unbound",
        "Bring an explicitly identified window to the foreground.",
    ),
    "MINIMIZE_WINDOW": ActionSpec(
        "MINIMIZE_WINDOW", "low", False, True, True,
        "pc-control.v131", "unbound",
        "Minimize an explicitly identified window.",
    ),
    "MAXIMIZE_WINDOW": ActionSpec(
        "MAXIMIZE_WINDOW", "low", False, True, True,
        "pc-control.v131", "unbound",
        "Maximize an explicitly identified window.",
    ),
    "CLOSE_WINDOW": ActionSpec(
        "CLOSE_WINDOW", "high", True, True, False,
        "pc-control.v131", "unbound",
        "Request close of an explicitly identified window; may lose unsaved work.",
    ),
    "TERMINATE_PROCESS": ActionSpec(
        "TERMINATE_PROCESS", "critical", True, True, False,
        "pc-control.v131", "unbound",
        "Terminate an explicitly identified process; destructive fallback only.",
    ),
}


def _safe_apps() -> frozenset[str]:
    try:
        from runtime.route_contract import OWNED_SAFE_DESKTOP_APPS
    except Exception as exc:
        raise PcControlContractError(
            "canonical safe-app ownership is unavailable"
        ) from exc
    apps = frozenset(
        str(item or "").strip().casefold()
        for item in OWNED_SAFE_DESKTOP_APPS
        if str(item or "").strip()
    )
    if not apps:
        raise PcControlContractError("canonical safe-app list is empty")
    return apps


def _request_id(action: str, params: Mapping[str, Any]) -> str:
    raw = json.dumps(
        {"action": action, "params": dict(params)},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return "pcr_" + hashlib.sha256(raw).hexdigest()[:20]


def _reject_raw_execution_fields(params: Mapping[str, Any]) -> None:
    bad = sorted(
        str(key)
        for key in params
        if str(key).strip().casefold() in DENIED_RAW_EXECUTION_KEYS
    )
    if bad:
        raise PcControlContractError(
            "raw shell/executable input is outside the W131 contract: "
            + ", ".join(bad)
        )


def _exact_keys(params: Mapping[str, Any], allowed: set[str]) -> None:
    extra = sorted(str(k) for k in params if str(k) not in allowed)
    if extra:
        raise PcControlContractError(
            "unexpected action parameters: " + ", ".join(extra)
        )


def _positive_int(value: Any, field: str, *, minimum: int = 1) -> int:
    if isinstance(value, bool):
        raise PcControlContractError(f"{field} must be an integer")
    try:
        number = int(value)
    except Exception as exc:
        raise PcControlContractError(f"{field} must be an integer") from exc
    if number < minimum:
        raise PcControlContractError(f"{field} must be >= {minimum}")
    return number


def _human_label(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise PcControlContractError(
            f"{field} is required as human-readable confirmation context"
        )
    if len(text) > 512:
        raise PcControlContractError(f"{field} is too long")
    return text


def normalize_request(
    action: str,
    params: Mapping[str, Any] | None = None,
    *,
    origin: str = "local-core",
) -> dict[str, Any]:
    action = str(action or "").strip().upper()
    if action not in ALL_ACTIONS:
        raise PcControlContractError(f"unsupported PC action: {action or '<empty>'}")

    raw = dict(params or {})
    _reject_raw_execution_fields(raw)
    normalized: dict[str, Any]

    if action in READ_ONLY_ACTIONS:
        _exact_keys(raw, set())
        normalized = {}

    elif action == "OPEN_SAFE_APP":
        _exact_keys(raw, {"app"})
        app = str(raw.get("app") or "").strip().casefold()
        if app not in _safe_apps():
            raise PcControlContractError(
                f"app is outside canonical safe-app allowlist: {app or '<empty>'}"
            )
        normalized = {"app": app}

    elif action in WINDOW_ACTIONS:
        _exact_keys(raw, {"hwnd", "title"})
        hwnd = _positive_int(raw.get("hwnd"), "hwnd")
        title = _human_label(raw.get("title"), "title")
        normalized = {"hwnd": hwnd, "title": title}

    elif action == "TERMINATE_PROCESS":
        _exact_keys(raw, {"pid", "image_name"})
        pid = _positive_int(raw.get("pid"), "pid", minimum=5)
        image_name = _human_label(raw.get("image_name"), "image_name")
        normalized = {"pid": pid, "image_name": image_name}

    else:  # defensive fail closed
        raise PcControlContractError(f"action has no normalization policy: {action}")

    request_id = _request_id(action, normalized)
    spec = ACTION_SPECS[action]
    confirmation_phrase = (
        f"CONFIRM PC {request_id}" if spec.requires_confirmation else None
    )

    return {
        "schema": REQUEST_SCHEMA,
        "request_id": request_id,
        "action": action,
        "params": normalized,
        "origin": str(origin or "local-core"),
        "risk_tier": spec.risk_tier,
        "requires_confirmation": spec.requires_confirmation,
        "confirmation_phrase": confirmation_phrase,
        "mutating": spec.mutating,
        "reversible": spec.reversible,
        "owner": spec.owner,
        "executor_state": spec.executor_state,
    }


def plan_request(request: Mapping[str, Any]) -> dict[str, Any]:
    if str(request.get("schema") or "") != REQUEST_SCHEMA:
        raise PcControlContractError("invalid PC-control request schema")

    action = str(request.get("action") or "").strip().upper()
    spec = ACTION_SPECS.get(action)
    if spec is None:
        raise PcControlContractError("unknown action in PC-control request")

    if request.get("request_id") != _request_id(
        action, request.get("params") or {}
    ):
        raise PcControlContractError("PC-control request identity mismatch")

    if spec.requires_confirmation:
        status = "WAITING_CONFIRMATION"
    elif spec.executor_state == "delegated":
        status = "DELEGATE_EXISTING_OWNER"
    else:
        status = "CONTRACT_READY_EXECUTOR_UNBOUND"

    return {
        "schema": PLAN_SCHEMA,
        "request_id": request["request_id"],
        "action": action,
        "status": status,
        "owner": spec.owner,
        "executor_state": spec.executor_state,
        "requires_confirmation": spec.requires_confirmation,
        "confirmation_phrase": request.get("confirmation_phrase"),
        "can_execute_here": False,
        "reason": (
            "W131-1 defines typed ownership and safety only; "
            "native execution is intentionally not bound yet."
        ),
    }


def capability_snapshot() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "actions": {
            name: asdict(ACTION_SPECS[name])
            for name in sorted(ACTION_SPECS)
        },
        "canonical_safe_apps": sorted(_safe_apps()),
        "file_operations_owner": "integrations.files.provider",
        "arbitrary_shell_input": False,
        "arbitrary_executable_input": False,
        "native_executor_bound": False,
        "receipts_required_when_bound": True,
        "typed_targets_required": True,
        "destructive_confirmation_required": True,
        "w132_recovery_acceptance_separate": True,
    }
