from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tools.models import ToolSource


@dataclass(frozen=True)
class AgentStep:
    """One validated tool call in an agent plan."""

    id: str
    tool: str
    action: str
    args: dict[str, Any] = field(default_factory=dict)
    category: str = ""
    description: str = ""


@dataclass(frozen=True)
class AgentPlan:
    """A bounded, structured multi-tool plan.

    `source` records how the plan was produced. The deterministic planner stays
    the zero-latency first path; v0.7.1.1 can add a strict small-model JSON
    plan without changing the executor/security contract.
    """

    objective: str
    steps: tuple[AgentStep, ...]
    source: str = "deterministic"
    stop_on_error: bool = False

    @property
    def multi_step(self) -> bool:
        return len(self.steps) >= 2


@dataclass(frozen=True)
class AgentObservation:
    step_id: str
    tool: str
    action: str
    ok: bool
    response: str
    category: str
    source: str
    data: dict[str, Any] = field(default_factory=dict)
    sources: tuple[ToolSource, ...] = ()


@dataclass(frozen=True)
class AgentRunResult:
    ok: bool
    response: str
    observations: tuple[AgentObservation, ...]
    sources: tuple[ToolSource, ...] = ()
    complete: bool = True
    failed_steps: tuple[str, ...] = ()
    data: dict[str, Any] = field(default_factory=dict)
