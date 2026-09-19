import unittest
from pathlib import Path

from runtime.resource_guardian import ResourceGuardian


class FakeLLM:
    pass


class FakeVoice:
    def xtts_model_loaded(self):
        return False

    def release_heavy_models(self):
        return None


class PrewarmRaceV0662Tests(unittest.TestCase):
    def test_user_cancel_blocks_prewarm_before_start(self):
        guardian = ResourceGuardian(FakeLLM(), FakeVoice())
        guardian.request_xtts_prewarm_cancel()
        self.assertFalse(guardian.conditional_xtts_prewarm())
        self.assertEqual(guardian._xtts_prewarm_last_result, "cancelled-before-start")

    def test_reset_rearms_next_prewarm_attempt(self):
        guardian = ResourceGuardian(FakeLLM(), FakeVoice())
        guardian.request_xtts_prewarm_cancel()
        self.assertTrue(guardian._prewarm_cancel_requested.is_set())
        guardian.reset_xtts_prewarm_cancel()
        self.assertFalse(guardian._prewarm_cancel_requested.is_set())

    def test_ui_queues_message_until_warmup_thread_finishes(self):
        source = Path(__file__).resolve().parents[1] / "ui" / "main_window.py"
        text = source.read_text(encoding="utf-8")
        self.assertIn("def _defer_message_for_prewarm", text)
        self.assertIn("request_xtts_prewarm_cancel()", text)
        self.assertIn("if self._defer_message_for_prewarm(text):", text)
        cleanup = text.split("def _cleanup_warmup_thread", 1)[1].split("def _refresh_resource_status", 1)[0]
        self.assertIn("_pending_user_message", cleanup)
        self.assertIn("QTimer.singleShot", cleanup)


if __name__ == "__main__":
    unittest.main()
