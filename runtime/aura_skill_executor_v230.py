# AURA v2.3 active skill executor gateway
from __future__ import annotations

from importlib import import_module
from typing import Any, Callable, Mapping

from skills.contracts import SkillInvocationContext
from runtime.aura_skill_registry_v230 import get_skill_registry


class SkillExecutionError(RuntimeError):
    pass


def execute_registered_skill(
    command: str,
    payload: Mapping[str, Any] | None,
    dispatch_existing_command: Callable[[str, Mapping[str, Any]], Any],
    *,
    source: str = "skill-executor",
) -> Any:
    command = str(command)
    registry = get_skill_registry()
    resolution = registry.resolve_command(command)
    if resolution is None:
        raise SkillExecutionError(f"unregistered_or_disabled_skill_command:{command}")

    module_name = f"skills.{resolution.skill_id}.handler"
    module = import_module(module_name)
    invoke = getattr(module, "invoke", None)
    if not callable(invoke):
        raise SkillExecutionError(f"skill_handler_missing_invoke:{module_name}")

    context = SkillInvocationContext(
        dispatch_existing_command=dispatch_existing_command,
        source=str(source or "skill-executor"),
    )
    return invoke(context, command, dict(payload or {}))
