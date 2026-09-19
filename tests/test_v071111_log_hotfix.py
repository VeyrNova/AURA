from regression_compat import assert_version_at_least
import json
import unittest
from pathlib import Path

from agent.fast_router import FastStructuredRouter
from agent.planner import DeterministicAgentPlanner
from agent.tool_registry import AgentToolRegistry
from agent.tool_selector import AgentToolSelector
from config.settings import settings
from core.intent_manager import IntentManager
from core.router import ActionRouter
from tools.internet_manager import InternetToolManager


class _FakeLLM:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def generate(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return json.dumps(self.payload, ensure_ascii=False)


class _AllowAll:
    class Decision:
        allowed = True
        confirmation_required = False
    def authorize(self, *args, **kwargs):
        return self.Decision()


class _Tasks:
    def create_task(self, **kwargs):
        return 1
    def list_tasks(self, *args, **kwargs):
        return []


class V071111RuntimeLogHotfixTests(unittest.TestCase):
    def test_version_and_router_budget_defaults(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.1.1.1")
        self.assertEqual(settings.AGENT_ROUTER_NUM_CTX, settings.LLM_VOICE_NUM_CTX)
        self.assertLessEqual(settings.AGENT_ROUTER_NUM_PREDICT, 96)
        self.assertLessEqual(settings.AGENT_ROUTER_READ_TIMEOUT, 6.0)

    def test_incomplete_create_task_stays_deterministic(self):
        intent, params = IntentManager().detect("créé une tache")
        self.assertEqual(intent, "CREATE_TASK")
        self.assertEqual(params, {})
        router = ActionRouter(None, _Tasks(), None, _AllowAll())
        self.assertEqual(router.route(intent, params), "Quelle tâche veux-tu ajouter ?")

    def test_create_task_with_payload_is_captured(self):
        intent, params = IntentManager().detect("crée une tâche : envoyer le rapport vendredi")
        self.assertEqual(intent, "CREATE_TASK")
        self.assertEqual(params["raw"], "envoyer le rapport vendredi")

    def test_natural_route_weather_is_planned_without_llm(self):
        manager = InternetToolManager()
        planner = DeterministicAgentPlanner(manager, AgentToolRegistry.default_readonly())
        text = "Je vais de Vidauban à Toulon, j'aimerais connaître le trajet ainsi que la météo à l'arrivée."
        plan = planner.plan(text)
        self.assertIsNotNone(plan)
        self.assertEqual(plan.source, "deterministic-route-weather")
        self.assertEqual([step.tool for step in plan.steps], ["maps.directions", "weather"])
        self.assertEqual(plan.steps[0].args["origin"], "Vidauban")
        self.assertEqual(plan.steps[0].args["destination"], "Toulon")
        self.assertEqual(plan.steps[1].args["location"], "Toulon")

    def test_explicit_route_plus_weather_destination_is_planned_without_llm(self):
        manager = InternetToolManager()
        planner = DeterministicAgentPlanner(manager, AgentToolRegistry.default_readonly())
        plan = planner.plan("Itinéraire de Vidauban à Toulon et météo à la destination")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.source, "deterministic-route-weather")
        self.assertEqual(plan.steps[1].args["location"], "Toulon")

    def test_weather_arrival_pronoun_is_not_sent_to_geocoder(self):
        self.assertEqual(InternetToolManager._extract_weather_location("météo à l'arrivée"), "")
        self.assertEqual(InternetToolManager._extract_weather_location("météo sur place"), "")

    def test_fast_router_uses_hard_budget_and_non_stream(self):
        llm = _FakeLLM({
            "route": "agent", "confidence": 0.95,
            "steps": [
                {"tool": "maps.directions", "args": {"origin": "Vidauban", "destination": "Toulon"}},
                {"tool": "weather", "args": {"location": "Toulon"}},
            ],
        })
        router = FastStructuredRouter(llm, AgentToolRegistry.default_readonly())
        decision = router.route("Itinéraire de Vidauban à Toulon et météo à Toulon")
        self.assertEqual(decision.route, "agent")
        kwargs = llm.calls[0][1]
        self.assertTrue(kwargs["force_non_stream"])
        self.assertEqual(kwargs["read_timeout"], settings.AGENT_ROUTER_READ_TIMEOUT)
        self.assertEqual(kwargs["num_ctx"], settings.LLM_VOICE_NUM_CTX)

    def test_selector_does_not_guess_unknown_second_tool(self):
        selector = AgentToolSelector(AgentToolRegistry.default_readonly())
        self.assertFalse(selector.should_try_structured("Météo à Toulon puis fais autre chose"))

    def test_state_watchdog_tracks_agent_router_worker(self):
        source = (Path(__file__).resolve().parents[1] / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("router_running = bool(self._agent_router_thread", source)
        self.assertIn("elif self._agent_router_thread is not None and self._agent_router_thread.isRunning()", source)


if __name__ == "__main__":
    unittest.main()
