from __future__ import annotations

from typing import Any, Mapping

from skills.contracts import SkillInvocationContext


def invoke(
    context: SkillInvocationContext,
    command: str,
    payload: Mapping[str, Any] | None = None,
) -> Any:
    # Delegate to the already-validated dispatcher.
    # v2.3 foundation does not duplicate authorization or execution.
    return context.dispatch(command, payload)
