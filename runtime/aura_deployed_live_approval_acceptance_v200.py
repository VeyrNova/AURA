"""AURA A200-R22 controlled deployed live approval acceptance guard.

This companion contains no execution backend. It only defines the acceptance
safety contract and helpers used by the R22 invariant.

The real execution path remains:
R21 composer -> R20 preview -> R17 approval UI -> R18 transport -> R16 -> R15
-> R14 -> R13 -> MissionEngine -> R11/R9/R7/R5 -> canonical PC provider.
"""

from __future__ import annotations

from typing import Any


A200_R22_MARKER = "AURA_A200_R22_CONTROLLED_LIVE_UI_APPROVAL_SELF_WINDOW_RESTORE_V1"

LIVE_SELF_WINDOW_ONLY = True
EXPLICIT_HUMAN_APPROVAL_REQUIRED = True
EXPLICIT_R17_UI_CONFIRMATION_REQUIRED = True
SINGLE_REVERSIBLE_MUTATION_REQUIRED = True
LIVE_CAPABILITY = "pc.minimize_window"
AUTOMATIC_EXACT_RESTORE_REQUIRED = True
APPROVAL_ONE_USE_REQUIRED = True
CANONICAL_RECEIPTS_REQUIRED = True
MISSIONENGINE_COMPLETION_REQUIRED = True
CRASH_JOURNAL_CLEAR_REQUIRED = True

DIRECT_NATURAL_LANGUAGE_EXECUTION_ENABLED = False
AUTO_APPROVAL_ENABLED = False
AUTO_CANCEL_ENABLED = False
AUTONOMOUS_RETRY_ENABLED = False
AUTONOMOUS_MULTI_MUTATION_ENABLED = False
DESTRUCTIVE_EXECUTION_ENABLED = False
CLOSE_WINDOW_ENABLED = False
TERMINATE_PROCESS_ENABLED = False
SHELL_EXECUTION_ENABLED = False


class R22AcceptanceDenied(PermissionError):
    pass


def task_by_key(mission: Any, key: str) -> Any:
    for task in mission.tasks.values():
        if str(getattr(task, "key", "")) == str(key):
            return task
    raise KeyError(key)


def foreground_hwnd(task_result: Any) -> int:
    if not isinstance(task_result, dict):
        return 0
    output = task_result.get("output")
    if not isinstance(output, dict):
        return 0
    pc_result = output.get("pc_result")
    if not isinstance(pc_result, dict):
        return 0
    data = pc_result.get("data")
    if not isinstance(data, dict):
        return 0
    try:
        return int(data.get("hwnd") or 0)
    except Exception:
        return 0


def assert_r22_safety_contract() -> None:
    if not LIVE_SELF_WINDOW_ONLY:
        raise RuntimeError("R22 must target only its uniquely titled console")
    if not EXPLICIT_HUMAN_APPROVAL_REQUIRED:
        raise RuntimeError("R22 requires explicit human approval")
    if not EXPLICIT_R17_UI_CONFIRMATION_REQUIRED:
        raise RuntimeError("R22 requires the deployed R17 approval path")
    if not SINGLE_REVERSIBLE_MUTATION_REQUIRED:
        raise RuntimeError("R22 permits only one reversible mutation")
    if LIVE_CAPABILITY != "pc.minimize_window":
        raise RuntimeError("R22 live capability must remain minimize only")
    if not AUTOMATIC_EXACT_RESTORE_REQUIRED:
        raise RuntimeError("R22 exact restore is mandatory")
    if not APPROVAL_ONE_USE_REQUIRED:
        raise RuntimeError("R22 approval must be one-use")
    if not CANONICAL_RECEIPTS_REQUIRED:
        raise RuntimeError("R22 canonical receipts are mandatory")
    if not MISSIONENGINE_COMPLETION_REQUIRED:
        raise RuntimeError("R22 MissionEngine completion is mandatory")
    if not CRASH_JOURNAL_CLEAR_REQUIRED:
        raise RuntimeError("R22 crash journal must be clear after completion")
    if DIRECT_NATURAL_LANGUAGE_EXECUTION_ENABLED:
        raise RuntimeError("direct natural-language execution is disabled")
    if AUTO_APPROVAL_ENABLED or AUTO_CANCEL_ENABLED:
        raise RuntimeError("auto approval/cancel is disabled")
    if AUTONOMOUS_RETRY_ENABLED or AUTONOMOUS_MULTI_MUTATION_ENABLED:
        raise RuntimeError("autonomous retry/multi-mutation is disabled")
    if DESTRUCTIVE_EXECUTION_ENABLED:
        raise RuntimeError("destructive execution is disabled")
    if CLOSE_WINDOW_ENABLED or TERMINATE_PROCESS_ENABLED:
        raise RuntimeError("close/terminate remain disabled")
    if SHELL_EXECUTION_ENABLED:
        raise RuntimeError("runtime shell execution remains disabled")
