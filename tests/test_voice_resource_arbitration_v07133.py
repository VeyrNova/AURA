import unittest
from pathlib import Path

from config.settings import settings
from runtime.resource_guardian import ResourceGuardian
from regression_compat import assert_version_at_least


class DummyLLM:
    pass


class DummyVoice:
    pass


class VoiceResourceArbitrationV07133Tests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.1.3.3")

    def test_voice_brain_prewarm_refuses_while_xtts_lane_active(self):
        guardian = ResourceGuardian(DummyLLM(), DummyVoice())
        guardian._xtts_prewarm_active = True
        guardian._voice_llm_prewarm_cancel_requested.clear()
        self.assertFalse(guardian.conditional_voice_llm_prewarm())
        self.assertEqual(guardian._voice_llm_prewarm_last_result, "xtts-resource-busy")

    def test_ui_defers_against_actual_xtts_background_thread(self):
        source = Path("ui/main_window.py").read_text(encoding="utf-8")
        start = source.index("def _defer_message_for_prewarm")
        end = source.index("def _defer_message_for_voice_brain_prewarm", start)
        method = source[start:end]
        self.assertIn("_xtts_background_warmup_thread", method)
        self.assertIn("xtts_prewarm_active", method)
        self.assertNotIn("thread = self._warmup_thread", method)

    def test_xtts_cleanup_resumes_user_before_voice_prewarm(self):
        source = Path("ui/main_window.py").read_text(encoding="utf-8")
        start = source.index("def _cleanup_xtts_background_prewarm")
        end = source.index("def _start_fast_text_brain_prewarm", start)
        method = source[start:end]
        self.assertLess(method.index("pending = self._pending_user_message"), method.index("VOICE_BRAIN_POST_START_PREWARM"))
        self.assertIn("resuming deferred user message", method)

    def test_voice_brain_start_checks_xtts_lane(self):
        source = Path("ui/main_window.py").read_text(encoding="utf-8")
        start = source.index("def _start_voice_brain_prewarm")
        end = source.index("def _cleanup_voice_brain_warmup_thread", start)
        method = source[start:end]
        self.assertIn("_xtts_background_warmup_thread is not None", method)
        self.assertIn("resource_guardian.xtts_prewarm_active", method)


if __name__ == "__main__":
    unittest.main()
