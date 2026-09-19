from __future__ import annotations

import unittest
from pathlib import Path

from core.version import AURA_BUILD, AURA_RELEASE_CHANNEL, AURA_VERSION
from config.settings import settings
from tools.search_intent import is_visual_request

ROOT = Path(__file__).resolve().parents[1]


class RuntimeV2RC3AsyncVoiceTests(unittest.TestCase):
    def test_release_identity(self):
        self.assertEqual(AURA_VERSION, "0.7.2.1")
        self.assertEqual(AURA_BUILD, "2026.08.15.9")
        self.assertEqual(AURA_RELEASE_CHANNEL, "consolidation-rc3.2")

    def test_microphone_recovery_settings_exist_and_are_bounded(self):
        self.assertTrue(hasattr(settings, "MIC_RECOVERY_ENABLED"))
        self.assertGreaterEqual(settings.MIC_RECOVERY_INITIAL_DELAY_MS, 250)
        self.assertGreaterEqual(settings.MIC_RECOVERY_SECOND_DELAY_MS, 500)
        self.assertGreaterEqual(settings.MIC_RECOVERY_RETRY_DELAY_MS, 1000)

    def test_screen_oriented_discography_is_visual(self):
        self.assertTrue(is_visual_request("affiche la discographie de Deftones"))
        self.assertTrue(is_visual_request("montre la chronologie des albums"))
        self.assertGreaterEqual(settings.LLM_VISUAL_STRUCTURED_NUM_PREDICT, 800)

    def test_xtts_warmup_does_not_own_startup_gate(self):
        src = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8", errors="replace")
        cleanup = src[src.index("def _cleanup_warmup_thread"):src.index("def _start_xtts_background_prewarm")]
        self.assertIn('self._finish_startup_sequence(result="voice-warming")', cleanup)
        self.assertIn("self._start_xtts_background_prewarm", cleanup)
        self.assertLess(
            cleanup.index('self._finish_startup_sequence(result="voice-warming")'),
            cleanup.index("self._start_xtts_background_prewarm"),
        )

    def test_xtts_ui_state_is_non_blocking(self):
        src = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8", errors="replace")
        block = src[src.index("def _set_xtts_preload_ui_state"):src.index("@staticmethod\n    def _startup_completion_text")]
        self.assertIn("UI remains interactive", block)
        self.assertNotIn("set_input_enabled(False", block)
        self.assertNotIn("set_microphone_available(False", block)
        self.assertNotIn('self.orb.set_state("PRELOAD")', block)

    def test_user_text_is_accepted_while_voice_warms(self):
        src = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8", errors="replace")
        block = src[src.index("def _on_user_message"):src.index("def _defer_message_for_voice_brain_prewarm") if False else src.index("def _start_fast_agent_router")]
        self.assertIn("User message accepted while Camilla warms asynchronously", block)
        self.assertNotIn("Message ignored by XTTS preload UI gate", block)
        self.assertNotIn("if self._defer_message_for_prewarm(text):", block)

    def test_voice_identity_lock_defers_boot_phrase(self):
        src = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8", errors="replace")
        block = src[src.index("def _announce_startup_completion"):src.index("# Compatibility shim")]
        self.assertIn("Voice Identity Lock", block)
        self.assertIn("Camilla warming", block)
        self.assertIn("_startup_completion_speech_pending", block)

    def test_passive_microphone_recovery_does_not_start_recording(self):
        src = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8", errors="replace")
        block = src[src.index("def _schedule_microphone_recovery"):src.index("# ------------------------------------------------------------------\n    # Text / intent / LLM")]
        self.assertIn("passive device discovery", block)
        self.assertIn("voice_engine.status()", block)
        self.assertNotIn("start_listening", block)
        self.assertNotIn("recorder.start", block)


if __name__ == "__main__":
    unittest.main()
