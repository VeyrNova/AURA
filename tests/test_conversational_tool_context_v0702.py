from regression_compat import assert_version_at_least
import unittest

from config.settings import settings
from tools.conversation_context import ConversationalToolContext
from tools.internet_manager import InternetToolManager
from tools.models import ToolPlan, ToolResult


class FakeClock:
    def __init__(self):
        self.value = 1000.0
    def __call__(self):
        return self.value
    def advance(self, seconds):
        self.value += seconds


class ConversationalToolContextV0702Tests(unittest.TestCase):
    def test_version_is_v0702(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.2")

    def test_missing_weather_location_opens_pending_slot(self):
        ctx = ConversationalToolContext()
        plan = ToolPlan("weather", "WEB_WEATHER", {"location": "", "tomorrow": False}, "weather")
        ctx.observe(plan, ToolResult(False, "ville ?", "weather", "missing_location"))
        self.assertEqual(ctx.state.pending_slot, "location")
        self.assertEqual(ctx.state.tool, "weather")

    def test_bare_city_completes_pending_weather_slot(self):
        ctx = ConversationalToolContext()
        ctx.observe(
            ToolPlan("weather", "WEB_WEATHER", {"location": "", "tomorrow": False}, "weather"),
            ToolResult(False, "ville ?", "weather", "missing_location"),
        )
        plan = ctx.plan_followup("Vidauban")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.name, "weather")
        self.assertEqual(plan.args["location"], "Vidauban")
        self.assertFalse(plan.args["tomorrow"])

    def test_pending_tomorrow_keeps_temporal_constraint(self):
        ctx = ConversationalToolContext()
        ctx.observe(
            ToolPlan("weather", "WEB_WEATHER", {"location": "", "tomorrow": True}, "weather"),
            ToolResult(False, "ville ?", "weather", "missing_location"),
        )
        plan = ctx.plan_followup("Toulon")
        self.assertTrue(plan.args["tomorrow"])

    def test_successful_weather_allows_tomorrow_followup(self):
        ctx = ConversationalToolContext()
        base = ToolPlan("weather", "WEB_WEATHER", {"location": "Vidauban", "tomorrow": False}, "weather")
        ctx.observe(base, ToolResult(True, "ok", "weather", "open-meteo"))
        plan = ctx.plan_followup("et demain ?")
        self.assertEqual(plan.args["location"], "Vidauban")
        self.assertTrue(plan.args["tomorrow"])

    def test_successful_weather_allows_new_place_followup(self):
        ctx = ConversationalToolContext()
        base = ToolPlan("weather", "WEB_WEATHER", {"location": "Vidauban", "tomorrow": True}, "weather")
        ctx.observe(base, ToolResult(True, "ok", "weather", "open-meteo"))
        plan = ctx.plan_followup("et à Toulon ?")
        self.assertEqual(plan.args["location"], "Toulon")
        self.assertTrue(plan.args["tomorrow"])

    def test_today_followup_resets_tomorrow(self):
        ctx = ConversationalToolContext()
        base = ToolPlan("weather", "WEB_WEATHER", {"location": "Vidauban", "tomorrow": True}, "weather")
        ctx.observe(base, ToolResult(True, "ok", "weather", "open-meteo"))
        plan = ctx.plan_followup("et aujourd'hui ?")
        self.assertFalse(plan.args["tomorrow"])

    def test_pending_context_expires(self):
        clock = FakeClock()
        ctx = ConversationalToolContext(clock=clock)
        ctx._set_weather(pending_slot="location", ttl=5)
        clock.advance(6)
        self.assertIsNone(ctx.plan_followup("Vidauban"))
        self.assertFalse(ctx.state.active)

    def test_topic_change_clears_pending_slot(self):
        ctx = ConversationalToolContext()
        ctx._set_weather(pending_slot="location", ttl=120)
        self.assertIsNone(ctx.plan_followup("Quel est le score du match ce soir ?"))
        self.assertFalse(ctx.state.active)
        self.assertIsNone(ctx.plan_followup("Paris"))

    def test_cancel_clears_pending_slot(self):
        ctx = ConversationalToolContext()
        ctx._set_weather(pending_slot="location", ttl=120)
        self.assertIsNone(ctx.plan_followup("laisse tomber"))
        self.assertFalse(ctx.state.active)

    def test_weather_question_without_city_really_has_empty_location(self):
        manager = InternetToolManager()
        plan = manager.plan("Quelle météo fait-il aujourd'hui ?")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.name, "weather")
        self.assertEqual(plan.args["location"], "")

    def test_manager_uses_conversation_context_before_normal_planner(self):
        manager = InternetToolManager()
        missing = ToolPlan("weather", "WEB_WEATHER", {"location": "", "tomorrow": False}, "weather")
        manager.observe_result(missing, ToolResult(False, "ville ?", "weather", "missing_location"))
        plan = manager.plan("Vidauban")
        self.assertEqual(plan.name, "weather")
        self.assertEqual(plan.args["location"], "Vidauban")

    def test_context_is_not_persistent_memory(self):
        source = __import__('pathlib').Path(__file__).resolve().parents[1].joinpath('tools','conversation_context.py').read_text(encoding='utf-8')
        self.assertNotIn('Database(', source)
        self.assertNotIn('MemoryManager', source)


if __name__ == "__main__":
    unittest.main()
