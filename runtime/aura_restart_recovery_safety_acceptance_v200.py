"""AURA A200-R23 restart/stale/cancel/crash-recovery safety acceptance.

No execution authority is defined here. This companion only declares the
acceptance contract and small result helpers. Canonical authority remains in
R13/R14/R15, MissionEngine, R9-R11, R5 and the W131/W132 PC provider path.
"""

from __future__ import annotations

from typing import Any


A200_R23_MARKER = "AURA_A200_R23_RESTART_STALE_CANCEL_CRASH_RECOVERY_SAFETY_V1"

SELF_WINDOW_ONLY = True
EXPLICIT_HUMAN_APPROVAL_REQUIRED = True
STALE_APPROVAL_MUST_FAIL_CLOSED = True
CANCELLATION_BEFORE_MUTATION_REQUIRED = True
CRASH_AFTER_DISPATCH_RECOVERY_REQUIRED = True
STARTUP_RECOVERY_PRECEDENCE_REQUIRED = True
APPROVAL_REPLAY_AFTER_CRASH_DISABLED = True
SINGLE_LIVE_MUTATION_MAX = 1
LIVE_CAPABILITY = "pc.minimize_window"
EXACT_RESTORE_REQUIRED = True

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


def assert_r23_safety_contract() -> None:
    if not SELF_WINDOW_ONLY:
        raise RuntimeError("R23 target must remain its own uniquely titled console")
    if not EXPLICIT_HUMAN_APPROVAL_REQUIRED:
        raise RuntimeError("R23 requires explicit human approval")
    if not STALE_APPROVAL_MUST_FAIL_CLOSED:
        raise RuntimeError("stale approvals must fail closed")
    if not CANCELLATION_BEFORE_MUTATION_REQUIRED:
        raise RuntimeError("pre-mutation cancellation is mandatory")
    if not CRASH_AFTER_DISPATCH_RECOVERY_REQUIRED:
        raise RuntimeError("crash recovery acceptance is mandatory")
    if not STARTUP_RECOVERY_PRECEDENCE_REQUIRED:
        raise RuntimeError("startup recovery must take precedence")
    if not APPROVAL_REPLAY_AFTER_CRASH_DISABLED:
        raise RuntimeError("post-crash approval replay must remain disabled")
    if SINGLE_LIVE_MUTATION_MAX != 1:
        raise RuntimeError("R23 permits at most one live mutation")
    if LIVE_CAPABILITY != "pc.minimize_window":
        raise RuntimeError("R23 live capability must remain minimize only")
    if not EXACT_RESTORE_REQUIRED:
        raise RuntimeError("exact restore is mandatory")
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
