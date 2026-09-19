from __future__ import annotations

from collections import OrderedDict

from agent.context import AgentContext
from agent.schemas import AgentObservation, AgentPlan, AgentRunResult
from agent.tool_registry import AgentToolRegistry
from tools.internet_manager import InternetToolManager
from tools.models import ToolPlan, ToolSource


class AgentExecutor:
    """Sequential read-only executor for pre-authorized AgentPlans."""

    def __init__(self, internet_manager: InternetToolManager, registry: AgentToolRegistry):
        self.internet_manager = internet_manager
        self.registry = registry

    @staticmethod
    def _unique_sources(observations: list[AgentObservation]) -> tuple[ToolSource, ...]:
        unique: "OrderedDict[tuple[str, str, str], ToolSource]" = OrderedDict()
        for observation in observations:
            for source in observation.sources:
                key = (str(source.name), str(source.host), str(source.url))
                unique.setdefault(key, source)
        return tuple(unique.values())

    @staticmethod
    def _render(observations: list[AgentObservation]) -> str:
        lines = []
        for index, obs in enumerate(observations, start=1):
            status = "✓" if obs.ok else "⚠"
            label = obs.category.replace("_", " ").upper() or obs.tool.upper()
            lines.append(f"{status} {index}. {label}\n{obs.response.strip()}")
        return "\n\n".join(lines).strip()

    def execute(self, plan: AgentPlan) -> AgentRunResult:
        context = AgentContext()
        observations: list[AgentObservation] = []
        failed: list[str] = []

        for step in plan.steps:
            resolved_args = context.resolve(step.args)
            tool_plan = ToolPlan(
                name=("maps" if step.tool.startswith("maps.") else
                      "web_search" if step.tool == "web.search" else
                      "web_fetch" if step.tool == "web.fetch" else
                      "knowledge_reference" if step.tool.startswith("knowledge.reference") else
                      step.tool),
                action=step.action,
                args=resolved_args,
                category=step.category,
            )
            result = self.internet_manager.execute(tool_plan)
            observation = AgentObservation(
                step_id=step.id,
                tool=step.tool,
                action=step.action,
                ok=bool(result.ok),
                response=str(result.response or ""),
                category=str(result.category or step.category),
                source=str(result.source or ""),
                data=dict(result.data or {}),
                sources=tuple(result.sources or ()),
            )
            observations.append(observation)
            context.add(observation)
            if not observation.ok:
                failed.append(step.id)
                if plan.stop_on_error:
                    break

        complete = len(observations) == len(plan.steps)
        ok = complete and not failed
        sources = self._unique_sources(observations)
        return AgentRunResult(
            ok=ok,
            response=self._render(observations),
            observations=tuple(observations),
            sources=sources,
            complete=complete,
            failed_steps=tuple(failed),
            data={
                "objective": plan.objective,
                "plan_source": plan.source,
                "step_count": len(plan.steps),
                "executed_steps": len(observations),
            },
        )
