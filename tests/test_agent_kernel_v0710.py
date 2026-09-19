import tempfile
import unittest
from pathlib import Path

from agent.context import AgentContext
from agent.executor import AgentExecutor
from agent.orchestrator import AgentOrchestrator
from agent.planner import DeterministicAgentPlanner
from agent.result_validator import AgentPlanValidationError, AgentPlanValidator
from agent.schemas import AgentObservation, AgentPlan, AgentStep
from agent.tool_registry import AgentToolRegistry
from database.database import Database
from security.policy_engine import SecurityPolicyEngine
from tools.models import ToolPlan, ToolResult


class _FakeInternetManager:
    def __init__(self):
        self.calls = []

    def execute(self, plan: ToolPlan):
        self.calls.append(plan)
        if plan.action == "MAPS_LOCATE":
            return ToolResult(True, "Toulon localisé.", "maps", "fake", data={"label": "Toulon"})
        if plan.action == "WEB_WEATHER":
            return ToolResult(True, f"Météo pour {plan.args['location']}.", "weather", "fake", data={"temp": 30})
        return ToolResult(False, "échec", plan.category, "fake")


class _PlannerInternet:
    def __init__(self):
        # Reuse the real deterministic planner without making requests.
        from tools.internet_manager import InternetToolManager
        self.real = InternetToolManager()

    def plan(self, text):
        return self.real.plan(text)


class AgentKernelV0710Tests(unittest.TestCase):
    def test_registry_is_explicit_and_read_only(self):
        registry = AgentToolRegistry.default_readonly()
        self.assertIsNotNone(registry.by_action("WEB_WEATHER"))
        self.assertIsNotNone(registry.by_action("MAPS_DIRECTIONS"))
        self.assertIsNone(registry.by_action("RUN_PROGRAM"))
        self.assertTrue(all(spec.read_only for spec in registry.specs()))

    def test_planner_builds_two_tool_plan(self):
        registry = AgentToolRegistry.default_readonly()
        planner = DeterministicAgentPlanner(_PlannerInternet().real, registry, max_steps=6)
        plan = planner.plan("Montre-moi Toulon sur la carte puis météo à Toulon")
        self.assertIsNotNone(plan)
        self.assertEqual([step.action for step in plan.steps], ["MAPS_LOCATE", "WEB_WEATHER"])

    def test_planner_understands_action_et_sequence(self):
        registry = AgentToolRegistry.default_readonly()
        planner = DeterministicAgentPlanner(_PlannerInternet().real, registry, max_steps=6)
        plan = planner.plan("Montre-moi Toulon sur la carte et donne-moi la météo à Toulon")
        self.assertIsNotNone(plan)
        self.assertEqual(len(plan.steps), 2)

    def test_single_tool_does_not_hijack_legacy_flow(self):
        registry = AgentToolRegistry.default_readonly()
        planner = DeterministicAgentPlanner(_PlannerInternet().real, registry, max_steps=6)
        self.assertIsNone(planner.plan("Météo à Toulon"))

    def test_unknown_action_is_rejected(self):
        registry = AgentToolRegistry.default_readonly()
        validator = AgentPlanValidator(registry, max_steps=6)
        plan = AgentPlan("bad", (
            AgentStep("step1", "maps.locate", "MAPS_LOCATE", {"query": "Toulon"}),
            AgentStep("step2", "system.shell", "RUN_PROGRAM", {"command": "calc"}),
        ))
        with self.assertRaises(AgentPlanValidationError):
            validator.validate(plan)

    def test_context_resolves_only_previous_observations(self):
        context = AgentContext()
        context.add(AgentObservation(
            "step1", "maps.locate", "MAPS_LOCATE", True, "ok", "maps", "fake",
            data={"label": "Toulon", "nested": {"value": 42}},
        ))
        self.assertEqual(context.resolve("${step1.data.label}"), "Toulon")
        self.assertEqual(context.resolve({"x": "${step1.data.nested.value}"})["x"], "42")
        self.assertEqual(context.resolve("${missing.data.x}"), "")

    def test_executor_runs_in_order_and_aggregates(self):
        fake = _FakeInternetManager()
        registry = AgentToolRegistry.default_readonly()
        executor = AgentExecutor(fake, registry)
        plan = AgentPlan("test", (
            AgentStep("step1", "maps.locate", "MAPS_LOCATE", {"query": "Toulon"}, "maps"),
            AgentStep("step2", "weather", "WEB_WEATHER", {"location": "${step1.data.label}"}, "weather"),
        ))
        result = executor.execute(plan)
        self.assertTrue(result.ok)
        self.assertEqual([call.action for call in fake.calls], ["MAPS_LOCATE", "WEB_WEATHER"])
        self.assertEqual(fake.calls[1].args["location"], "Toulon")
        self.assertIn("Toulon localisé", result.response)
        self.assertIn("Météo pour Toulon", result.response)

    def test_security_authorizes_each_readonly_step(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            db = Database(Path(tmp.name) / "aura.db")
            security = SecurityPolicyEngine(db)
            fake = _FakeInternetManager()
            # AgentOrchestrator expects planner methods but authorization can be
            # tested independently of actual network execution.
            orchestrator = AgentOrchestrator.__new__(AgentOrchestrator)
            orchestrator.security_engine = security
            plan = AgentPlan("test", (
                AgentStep("step1", "maps.locate", "MAPS_LOCATE", {"query": "Toulon"}, "maps"),
                AgentStep("step2", "weather", "WEB_WEATHER", {"location": "Toulon"}, "weather"),
            ))
            self.assertIs(orchestrator.authorize(plan), plan)
            rows = db.conn.execute("SELECT action, allowed FROM security_audit ORDER BY id").fetchall()
            self.assertEqual([row["action"] for row in rows[-2:]], ["MAPS_LOCATE", "WEB_WEATHER"])
            self.assertTrue(all(row["allowed"] == 1 for row in rows[-2:]))
            db.close()
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
