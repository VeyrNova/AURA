import unittest
from unittest.mock import patch

from ai.voice_routing import VoiceRoute, classify_voice_route
from config.settings import _env_float_upgrade, _env_int_upgrade, settings
from runtime.memory_policy import MemoryAction, MemoryPressureStateMachine
from runtime.resource_guardian import ResourceGuardian, ResourceSnapshot
from ui.response_presentation import for_llm_reply, for_tool_result
from tools.models import ToolPlan, ToolResult, ToolSource
from voice.xtts_tts import XTTSTTS


class MemoryPolicyTests(unittest.TestCase):
    def test_90_percent_keeps_hot_voice_brain(self):
        s = MemoryPressureStateMachine()
        d = s.evaluate(ram_percent=90.2, available_gib=1.55, voice_brain_loaded=True, xtts_hot=True)
        self.assertEqual(d.action, MemoryAction.KEEP_RESIDENT)

    def test_soft_pressure_trims_but_keeps_model(self):
        s = MemoryPressureStateMachine()
        d = s.evaluate(ram_percent=92.0, available_gib=1.45, voice_brain_loaded=True, xtts_hot=True)
        self.assertEqual(d.action, MemoryAction.TRIM_OPTIONAL)

    def test_critical_unloads(self):
        s = MemoryPressureStateMachine()
        d = s.evaluate(ram_percent=94.2, available_gib=0.95, voice_brain_loaded=True, xtts_hot=True)
        self.assertEqual(d.action, MemoryAction.UNLOAD_VOICE_BRAIN)
        self.assertTrue(d.pressure_latched)

    def test_predicted_90_percent_prewarm_is_refused_in_soft_zone(self):
        s = MemoryPressureStateMachine()
        d = s.evaluate(
            ram_percent=63.0, available_gib=5.7, voice_brain_loaded=False, xtts_hot=True,
            predicted_with_voice_percent=89.0, predicted_available_after_gib=1.7,
        )
        self.assertFalse(d.allow_voice_prewarm)

    def test_low_current_ram_can_still_prewarm_under_91_percent(self):
        s = MemoryPressureStateMachine()
        d = s.evaluate(
            ram_percent=52.0, available_gib=6.0, voice_brain_loaded=False, xtts_hot=True,
            predicted_with_voice_percent=86.0, predicted_available_after_gib=2.2,
        )
        self.assertTrue(d.allow_voice_prewarm)

    def test_65_percent_current_ram_blocks_background_prewarm(self):
        s = MemoryPressureStateMachine()
        d = s.evaluate(
            ram_percent=65.2, available_gib=5.5, voice_brain_loaded=False, xtts_hot=True,
            predicted_with_voice_percent=90.8, predicted_available_after_gib=1.44,
        )
        self.assertFalse(d.allow_voice_prewarm)


class LegacyEnvMigrationTests(unittest.TestCase):
    def test_stock_v07014_ram_threshold_is_upgraded(self):
        with patch.dict("os.environ", {"RESOURCE_RAM_CRITICAL_PCT": "88"}, clear=False):
            self.assertEqual(_env_float_upgrade("RESOURCE_RAM_CRITICAL_PCT", 94, (88,)), 94.0)

    def test_non_stock_custom_threshold_is_preserved(self):
        with patch.dict("os.environ", {"RESOURCE_RAM_CRITICAL_PCT": "92.5"}, clear=False):
            self.assertEqual(_env_float_upgrade("RESOURCE_RAM_CRITICAL_PCT", 94, (88,)), 92.5)

    def test_stock_realtime_limit_is_upgraded(self):
        with patch.dict("os.environ", {"REALTIME_DIALOGUE_MAX_RAM_PCT": "87"}, clear=False):
            self.assertEqual(_env_float_upgrade("REALTIME_DIALOGUE_MAX_RAM_PCT", 92, (87,)), 92.0)

    def test_stock_history_limit_is_upgraded(self):
        with patch.dict("os.environ", {"LLM_VOICE_MAX_HISTORY_MESSAGES": "6"}, clear=False):
            self.assertEqual(_env_int_upgrade("LLM_VOICE_MAX_HISTORY_MESSAGES", 4, (6,)), 4)


class RoutingTests(unittest.TestCase):
    def test_greeting_voice(self):
        self.assertEqual(classify_voice_route("Bonsoir, comment vas-tu ?"), VoiceRoute.VOICE_BRAIN)

    def test_explanation_text_brain(self):
        self.assertEqual(classify_voice_route("Pourquoi le ciel est bleu ?"), VoiceRoute.TEXT_BRAIN)

    def test_personal_conversation_stays_fast(self):
        self.assertEqual(classify_voice_route("Tu te souviens de mon prénom ?"), VoiceRoute.VOICE_BRAIN)


class PresentationTests(unittest.TestCase):
    def test_long_llm_reply_becomes_visual(self):
        d = for_llm_reply("x" * (settings.VISUAL_RESULT_MIN_CHARS + 1), "explique")
        self.assertTrue(d.visual)
        self.assertIn("affiche", d.speech.lower())

    def test_web_search_is_always_visual(self):
        result = ToolResult(
            True, "résultats", "web_search", "brave-search",
            (ToolSource("Exemple", "example.com", "2026-08-09T07:00", "https://example.com"),),
        )
        plan = ToolPlan("web_search", "WEB_SEARCH", {"query": "test"}, "web_search")
        d = for_tool_result(result, plan)
        self.assertTrue(d.visual)
        self.assertIn("RÉSULTATS", d.title)


class ChunkingRegressionTests(unittest.TestCase):
    def test_tiny_final_chunk_never_remerges_into_first_chunk(self):
        text = "Première phrase assez longue pour être autonome. Deuxième phrase également autonome. Fin."
        plan = XTTSTTS._natural_chunk_plan(text, first_limit=48, next_limit=60, min_chars=32, max_chunks=8)
        self.assertEqual(" ".join(item.text for item in plan), text)
        if len(plan) >= 2:
            self.assertLess(len(plan[0].text), len(text))


if __name__ == "__main__":
    unittest.main()
