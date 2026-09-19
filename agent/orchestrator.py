from __future__ import annotations

import logging

from agent.executor import AgentExecutor
from agent.fast_router import FastStructuredRouter
from agent.loop_guard import AgentLoopGuard, AgentLoopGuardError
from agent.planner import DeterministicAgentPlanner
from agent.result_validator import AgentPlanValidationError, AgentPlanValidator
from agent.schemas import AgentPlan, AgentRunResult
from agent.tool_registry import AgentToolRegistry
from security.policy_engine import SecurityPolicyEngine
from tools.internet_manager import InternetToolManager
from tools.models import ToolResult
from ai.llm_manager import LLMManager
from config.settings import settings

logger = logging.getLogger("aura.agent")


class AgentOrchestrator:
    """Security-bounded planning + execution facade used by AuraCore."""

    def __init__(
        self,
        internet_manager: InternetToolManager,
        security_engine: SecurityPolicyEngine,
        *,
        llm_manager: LLMManager | None = None,
        max_steps: int = 6,
    ):
        self.internet_manager = internet_manager
        self.security_engine = security_engine
        self.registry = AgentToolRegistry.default_readonly()
        self.planner = DeterministicAgentPlanner(
            internet_manager, self.registry, max_steps=max_steps,
        )
        self.validator = AgentPlanValidator(self.registry, max_steps=max_steps)
        self.loop_guard = AgentLoopGuard(
            max_same_signature=settings.AGENT_LOOP_MAX_SAME_SIGNATURE,
            max_same_action=settings.AGENT_LOOP_MAX_SAME_ACTION,
        )
        self.executor = AgentExecutor(internet_manager, self.registry)
        self.fast_router = (
            FastStructuredRouter(
                llm_manager, self.registry, max_steps=max_steps,
                selector_max_tools=settings.AGENT_TOOL_SELECTOR_MAX,
            )
            if llm_manager is not None else None
        )

    def plan(self, text: str) -> AgentPlan | None:
        plan = self.planner.plan(text)
        if plan is None:
            return None
        try:
            return self.loop_guard.validate(self.validator.validate(plan))
        except (AgentPlanValidationError, AgentLoopGuardError) as exc:
            logger.warning("Agent plan rejected validation/loop guard: %s", exc)
            return None


    def should_try_fast_router(self, text: str) -> bool:
        return bool(self.fast_router is not None and self.fast_router.should_try(text))

    def plan_fast_router(self, text: str) -> AgentPlan | None:
        if self.fast_router is None:
            return None
        decision = self.fast_router.route(text)
        if decision.plan is None:
            return None
        try:
            return self.loop_guard.validate(self.validator.validate(decision.plan))
        except (AgentPlanValidationError, AgentLoopGuardError) as exc:
            logger.warning("Fast router plan rejected: %s", exc)
            return None

    def authorize(self, plan: AgentPlan) -> AgentPlan | None:
        """Authorize every step on the main/UI thread before worker execution."""
        for step in plan.steps:
            decision = self.security_engine.authorize(step.action, step.args)
            if not decision.allowed:
                logger.warning(
                    "Agent plan denied step=%s action=%s reason=%s",
                    step.id, step.action, decision.reason,
                )
                return None
        return plan

    def execute(self, plan: AgentPlan) -> AgentRunResult:
        # Execution must receive only a previously validated+authorized plan.
        validated = self.loop_guard.validate(self.validator.validate(plan))
        return self.executor.execute(validated)

    @staticmethod
    def as_tool_result(run: AgentRunResult) -> ToolResult:
        return ToolResult(
            ok=run.ok,
            response=run.response,
            category="agent",
            source="agent-kernel",
            sources=run.sources,
            speech_response="",
            item_count=len(run.observations),
            expected_items=len(run.observations),
            complete=run.complete,
            data={
                **run.data,
                "observations": [
                    {
                        "step_id": obs.step_id,
                        "tool": obs.tool,
                        "action": obs.action,
                        "ok": obs.ok,
                        "response": obs.response,
                        "category": obs.category,
                        "source": obs.source,
                        "data": obs.data,
                    }
                    for obs in run.observations
                ],
                "failed_steps": list(run.failed_steps),
            },
        )
