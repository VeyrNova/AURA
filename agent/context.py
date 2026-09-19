from __future__ import annotations

import re
from typing import Any

from agent.schemas import AgentObservation

_REF_RE = re.compile(r"\$\{(?P<step>[A-Za-z0-9_-]+)\.(?P<path>[A-Za-z0-9_.-]+)\}")


class AgentContext:
    """Runtime observations + safe placeholder resolution.

    There is deliberately no eval(), attribute access or arbitrary expression
    language. A future planner may reference only previous observation fields.
    """

    def __init__(self):
        self._observations: dict[str, AgentObservation] = {}

    def add(self, observation: AgentObservation) -> None:
        self._observations[observation.step_id] = observation

    def get(self, step_id: str) -> AgentObservation | None:
        return self._observations.get(step_id)

    @staticmethod
    def _walk(value: Any, path: str) -> Any:
        current = value
        for part in path.split("."):
            if isinstance(current, dict):
                if part not in current:
                    return ""
                current = current[part]
            else:
                return ""
        return current

    def _resolve_match(self, match: re.Match[str]) -> str:
        observation = self.get(match.group("step"))
        if observation is None:
            return ""
        path = match.group("path")
        root: dict[str, Any] = {
            "response": observation.response,
            "source": observation.source,
            "category": observation.category,
            "ok": observation.ok,
            "data": observation.data,
        }
        value = self._walk(root, path)
        if isinstance(value, (dict, list, tuple)):
            return str(value)
        return str(value if value is not None else "")

    def resolve(self, value: Any) -> Any:
        if isinstance(value, str):
            return _REF_RE.sub(self._resolve_match, value)
        if isinstance(value, dict):
            return {str(k): self.resolve(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.resolve(v) for v in value]
        if isinstance(value, tuple):
            return tuple(self.resolve(v) for v in value)
        return value
