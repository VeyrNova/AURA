from __future__ import annotations

from regression_compat import assert_version_at_least
import unittest
from unittest.mock import patch

from ai.visual_routing import select_visual_profile
from config.settings import settings
from tools.internet_manager import InternetToolManager
from tools.search_intent import (
    extract_visual_search_query,
    is_complex_visual_analysis,
    is_visual_request,
)


class V070153VisualToolFirstTests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.15.6.10")

    def test_real_world_places_list_is_tool_first(self):
        text = "donne 5 lieux à visiter autour de Vidauban"
        self.assertTrue(is_visual_request(text))
        self.assertEqual(extract_visual_search_query(text), text)
        with patch.object(settings, "WEB_SEARCH_ENABLED", True):
            manager = InternetToolManager()
            plan = manager.plan(text)
        self.assertIsNotNone(plan)
        self.assertEqual(plan.name, "web_search")
        self.assertEqual(plan.args["count"], 5)
        self.assertIn("Vidauban", plan.args["query"])

    def test_real_world_restaurant_list_is_tool_first(self):
        text = "donne-moi 4 restaurants autour de Nice"
        self.assertTrue(is_visual_request(text))
        self.assertIsNotNone(extract_visual_search_query(text))
        with patch.object(settings, "WEB_SEARCH_ENABLED", True):
            plan = InternetToolManager().plan(text)
        self.assertIsNotNone(plan)
        self.assertEqual(plan.name, "web_search")
        self.assertEqual(plan.args["count"], 4)

    def test_creative_list_is_not_forced_to_web(self):
        text = "donne 5 idées de titres pour une chanson cyberpunk"
        self.assertTrue(is_visual_request(text))
        self.assertIsNone(extract_visual_search_query(text))
        with patch.object(settings, "WEB_SEARCH_ENABLED", True):
            plan = InternetToolManager().plan(text)
        self.assertIsNone(plan)

    def test_complex_visual_analysis_is_explicit_only(self):
        self.assertTrue(is_complex_visual_analysis("fais une analyse approfondie de ces options"))
        self.assertFalse(is_complex_visual_analysis("donne 5 idées de titres"))


class _FakeGuardian:
    def __init__(self):
        self.calls = []

    def llm_request_profile(self, *, voice_output: bool):
        self.calls.append(bool(voice_output))
        if voice_output:
            return {
                "name": "voice-fast",
                "model": "llama3.2:3b",
                "keep_alive": "5m",
                "num_ctx": 2048,
                "num_predict": 104,
                "temperature": 0.42,
                "top_p": 0.82,
                "compact": True,
                "co_resident": True,
            }
        return {
            "name": "text",
            "model": "llama3.1",
            "keep_alive": "2m",
            "num_ctx": 4096,
            "num_predict": 220,
            "temperature": 0.62,
            "top_p": 0.90,
            "compact": False,
            "co_resident": False,
        }


class V070153VisualProfileTests(unittest.TestCase):
    def test_normal_non_tool_visual_uses_warm_voice_brain_without_voice_brevity(self):
        guardian = _FakeGuardian()
        profile = select_visual_profile(guardian, "donne 5 idées de titres pour une chanson cyberpunk")
        self.assertEqual(guardian.calls, [True])
        self.assertEqual(profile["name"], "visual-fast")
        self.assertEqual(profile["model"], "llama3.2:3b")
        self.assertTrue(profile["co_resident"])
        self.assertGreaterEqual(profile["num_predict"], settings.LLM_VISUAL_FAST_NUM_PREDICT)

    def test_explicit_deep_visual_analysis_can_use_text_brain(self):
        guardian = _FakeGuardian()
        profile = select_visual_profile(guardian, "fais une analyse approfondie de ces options")
        self.assertEqual(guardian.calls, [False])
        self.assertEqual(profile["name"], "visual-deep")
        self.assertEqual(profile["model"], "llama3.1")
        self.assertGreaterEqual(profile["num_predict"], settings.LLM_VISUAL_NUM_PREDICT)


if __name__ == "__main__":
    unittest.main()
