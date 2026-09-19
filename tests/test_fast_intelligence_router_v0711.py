from regression_compat import assert_version_at_least
import json
import unittest

from agent.fast_router import FastStructuredRouter
from agent.loop_guard import AgentLoopGuard, AgentLoopGuardError
from agent.result_validator import AgentPlanValidationError, AgentPlanValidator
from agent.schemas import AgentPlan, AgentStep
from agent.tool_registry import AgentToolRegistry
from agent.tool_selector import AgentToolSelector
from config.settings import settings


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        if isinstance(self.payload, str):
            return self.payload
        return json.dumps(self.payload, ensure_ascii=False)


class FastIntelligenceRouterV0711Tests(unittest.TestCase):
    def setUp(self):
        self.registry = AgentToolRegistry.default_readonly()

    def test_version_and_router_defaults(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.1.1")
        self.assertTrue(settings.AGENT_LLM_PLANNER_ENABLED)
        self.assertEqual(settings.AGENT_ROUTER_MODEL, settings.LLM_VOICE_MODEL)
        self.assertLessEqual(settings.AGENT_ROUTER_NUM_PREDICT, 256)
        self.assertTrue(settings.AGENT_ROUTER_PRESERVE_HOT_XTTS)

    def test_ui_router_preserves_hot_xtts_before_optional_load(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("Fast Intelligence Router skipped: preserving hot XTTS residency", source)
        self.assertIn("AGENT_ROUTER_PRESERVE_HOT_XTTS", source)


    def test_selector_does_not_tax_single_weather_request(self):
        selector = AgentToolSelector(self.registry)
        self.assertFalse(selector.should_try_structured("Quelle est la météo à Toulon ?"))

    def test_selector_detects_ambiguous_route_plus_weather(self):
        selector = AgentToolSelector(self.registry)
        text = "Je vais de Vidauban à Toulon, donne-moi l'itinéraire et la météo à destination"
        self.assertTrue(selector.should_try_structured(text))
        names = {spec.name for spec in selector.select(text)}
        self.assertIn("maps.directions", names)
        self.assertIn("weather", names)

    def test_router_builds_strict_plan_from_small_json(self):
        llm = FakeLLM({
            "route": "agent",
            "complexity": "fast",
            "need_memory": False,
            "confidence": 0.96,
            "speech_ack": "Je regarde.",
            "steps": [
                {"tool": "maps.directions", "args": {"origin": "Vidauban", "destination": "Toulon"}},
                {"tool": "weather", "args": {"location": "Toulon", "tomorrow": False}},
            ],
        })
        router = FastStructuredRouter(llm, self.registry)
        decision = router.route("Je vais de Vidauban à Toulon, donne-moi l'itinéraire et la météo à destination")
        self.assertEqual(decision.route, "agent")
        self.assertEqual(decision.plan.source, "fast-structured-router")
        self.assertEqual([s.tool for s in decision.plan.steps], ["maps.directions", "weather"])
        self.assertEqual(llm.calls[0][1]["model"], settings.AGENT_ROUTER_MODEL)

    def test_router_rejects_tool_not_preselected(self):
        llm = FakeLLM({
            "route": "agent", "confidence": 0.99,
            "steps": [
                {"tool": "web.fetch", "args": {"url": "https://evil.example/"}},
                {"tool": "weather", "args": {"location": "Toulon"}},
            ],
        })
        router = FastStructuredRouter(llm, self.registry)
        decision = router.route("Itinéraire vers Toulon et météo à Toulon")
        self.assertEqual(decision.route, "legacy")
        self.assertIsNone(decision.plan)

    def test_router_rejects_invented_fetch_url(self):
        llm = FakeLLM({
            "route": "agent", "confidence": 0.99,
            "steps": [
                {"tool": "web.fetch", "args": {"url": "https://invented.example/"}},
                {"tool": "web.search", "args": {"query": "exemple"}},
            ],
        })
        router = FastStructuredRouter(llm, self.registry)
        decision = router.route("Lis https://example.com puis recherche exemple")
        self.assertEqual(decision.route, "legacy")

    def test_router_rejects_fake_multistep_with_one_domain_only(self):
        llm = FakeLLM({
            "route": "agent", "confidence": 0.99,
            "steps": [
                {"tool": "knowledge.reference.local", "args": {"subject": "ciel bleu"}},
                {"tool": "knowledge.reference.web", "args": {"subject": "ciel bleu"}},
            ],
        })
        router = FastStructuredRouter(llm, self.registry)
        decision = router.route("Explique pourquoi le ciel est bleu et donne la météo à Toulon")
        self.assertEqual(decision.route, "legacy")


    def test_low_confidence_falls_back(self):
        llm = FakeLLM({
            "route": "agent", "confidence": 0.20,
            "steps": [
                {"tool": "maps.directions", "args": {"destination": "Toulon"}},
                {"tool": "weather", "args": {"location": "Toulon"}},
            ],
        })
        router = FastStructuredRouter(llm, self.registry)
        decision = router.route("Itinéraire vers Toulon et météo à Toulon")
        self.assertEqual(decision.route, "legacy")

    def test_loop_guard_rejects_abab_cycle(self):
        steps = (
            AgentStep("step1", "weather", "WEB_WEATHER", {"location": "Toulon"}, "weather"),
            AgentStep("step2", "maps.locate", "MAPS_LOCATE", {"query": "Toulon"}, "maps"),
            AgentStep("step3", "weather", "WEB_WEATHER", {"location": "Toulon"}, "weather"),
            AgentStep("step4", "maps.locate", "MAPS_LOCATE", {"query": "Toulon"}, "maps"),
        )
        with self.assertRaises(AgentLoopGuardError):
            AgentLoopGuard().validate(AgentPlan("cycle", steps))

    def test_validator_rejects_future_step_reference(self):
        plan = AgentPlan("bad ref", (
            AgentStep("step1", "weather", "WEB_WEATHER", {"location": "${step2.data.label}"}, "weather"),
            AgentStep("step2", "maps.locate", "MAPS_LOCATE", {"query": "Toulon"}, "maps"),
        ))
        with self.assertRaises(AgentPlanValidationError):
            AgentPlanValidator(self.registry).validate(plan)

    def test_validator_accepts_previous_step_reference(self):
        plan = AgentPlan("good ref", (
            AgentStep("step1", "maps.locate", "MAPS_LOCATE", {"query": "Toulon"}, "maps"),
            AgentStep("step2", "weather", "WEB_WEATHER", {"location": "${step1.data.label}"}, "weather"),
        ))
        self.assertIs(AgentPlanValidator(self.registry).validate(plan), plan)


if __name__ == "__main__":
    unittest.main()
