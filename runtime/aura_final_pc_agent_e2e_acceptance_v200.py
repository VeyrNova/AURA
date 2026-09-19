"""AURA A200-R24 final multi-step autonomous PC agent E2E acceptance guard.

This companion defines no new execution authority. It exists only to assert
the final supervised E2E acceptance contract.

Canonical execution remains:
user intent -> R20 preview -> R21 composer seam -> R17 explicit approval
-> R18/R16/R15/R14/R13 -> MissionEngine -> R11/R9/R7/R5 -> PC provider
-> W132 exact restore -> receipts/evidence -> final runtime ready state.
"""

from __future__ import annotations

from typing import Any

A200_R24_MARKER = "AURA_A200_R24_FINAL_MULTI_STEP_AUTONOMOUS_PC_AGENT_E2E_V1"

SELF_WINDOW_ONLY = True
EXPLICIT_HUMAN_APPROVAL_REQUIRED = True
EXPLICIT_R17_CONFIRM_REQUIRED = True
PLAN_PREVIEW_MUST_BE_NON_EXECUTABLE = True
MISSION_TASK_COUNT_REQUIRED = 5
EXPECTED_RECEIPT_COUNT = 8
SINGLE_LIVE_MUTATION_MAX = 1
LIVE_CAPABILITY = "pc.minimize_window"
EXACT_W132_RESTORE_REQUIRED = True
MISSIONENGINE_EVIDENCE_REQUIRED = True
FINAL_RUNTIME_READY_REQUIRED = True
APPROVAL_ONE_USE_REQUIRED = True
NO_PENDING_RECOVERY_REQUIRED = True

DIRECT_NATURAL_LANGUAGE_EXECUTION_ENABLED = False
AUTO_APPROVAL_ENABLED = False
AUTO_CANCEL_ENABLED = False
AUTONOMOUS_RETRY_ENABLED = False
AUTONOMOUS_MULTI_MUTATION_ENABLED = False
DESTRUCTIVE_EXECUTION_ENABLED = False
CLOSE_WINDOW_ENABLED = False
TERMINATE_PROCESS_ENABLED = False
SHELL_EXECUTION_ENABLED = False


def task_by_key(mission: Any, key: str) -> Any:
    for task in mission.tasks.values():
        if str(getattr(task, "key", "")) == str(key):
            return task
    raise KeyError(key)


def foreground_hwnd_from_task(task: Any) -> int:
    result = getattr(task, "result", None)
    if not isinstance(result, dict):
        return 0
    output = result.get("output")
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


def assert_r24_safety_contract() -> None:
    if not SELF_WINDOW_ONLY:
        raise RuntimeError("R24 live target must remain the unique R24 console")
    if not EXPLICIT_HUMAN_APPROVAL_REQUIRED:
        raise RuntimeError("R24 requires explicit human approval")
    if not EXPLICIT_R17_CONFIRM_REQUIRED:
        raise RuntimeError("R24 requires the real R17 approval path")
    if not PLAN_PREVIEW_MUST_BE_NON_EXECUTABLE:
        raise RuntimeError("R24 mutation preview must remain non-executable")
    if MISSION_TASK_COUNT_REQUIRED != 5:
        raise RuntimeError("R24 requires the certified five-task mission")
    if EXPECTED_RECEIPT_COUNT != 8:
        raise RuntimeError("R24 expects eight canonical receipts")
    if SINGLE_LIVE_MUTATION_MAX != 1:
        raise RuntimeError("R24 permits exactly one live mutation")
    if LIVE_CAPABILITY != "pc.minimize_window":
        raise RuntimeError("R24 live capability must remain minimize only")
    if not EXACT_W132_RESTORE_REQUIRED:
        raise RuntimeError("R24 exact W132 restore is mandatory")
    if not MISSIONENGINE_EVIDENCE_REQUIRED:
        raise RuntimeError("R24 MissionEngine evidence is mandatory")
    if not FINAL_RUNTIME_READY_REQUIRED:
        raise RuntimeError("R24 final runtime ready state is mandatory")
    if not APPROVAL_ONE_USE_REQUIRED:
        raise RuntimeError("R24 approval must be one-use")
    if not NO_PENDING_RECOVERY_REQUIRED:
        raise RuntimeError("R24 must end with no pending recovery")
    if DIRECT_NATURAL_LANGUAGE_EXECUTION_ENABLED:
        raise RuntimeError("direct natural-language execution is disabled")
    if AUTO_APPROVAL_ENABLED or AUTO_CANCEL_ENABLED:
        raise RuntimeError("automatic approval/cancel is disabled")
    if AUTONOMOUS_RETRY_ENABLED or AUTONOMOUS_MULTI_MUTATION_ENABLED:
        raise RuntimeError("autonomous retry/multi-mutation is disabled")
    if DESTRUCTIVE_EXECUTION_ENABLED:
        raise RuntimeError("destructive execution is disabled")
    if CLOSE_WINDOW_ENABLED or TERMINATE_PROCESS_ENABLED:
        raise RuntimeError("close/terminate remain disabled")
    if SHELL_EXECUTION_ENABLED:
        raise RuntimeError("runtime shell execution remains disabled")
