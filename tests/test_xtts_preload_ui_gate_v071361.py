import unittest
from pathlib import Path

from config.settings import settings


ROOT = Path(__file__).parents[1]
MAIN = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
CHAT = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")


class XTTSPreloadUIGateV071361Tests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(settings.APP_VERSION, "0.7.2")

    def test_preload_hud_state_and_ready_state_are_explicit(self):
        self.assertIn('self.status_label.setText("VOICE CORE BOOT")', MAIN)
        self.assertIn('XTTS v2 · RTX 4050 · INITIALISATION', MAIN)
        self.assertIn('XTTS READY · RTX 4050 · STREAMING', MAIN)
        self.assertIn('AURA PRÊTE', MAIN)

    def test_text_and_microphone_are_gated_until_background_prewarm_finishes(self):
        self.assertIn('self.chat_panel.set_input_enabled(False, placeholder="Initialisation du Voice Core XTTS sur RTX 4050…")', MAIN)
        self.assertIn('self.chat_panel.set_microphone_available(False)', MAIN)
        self.assertIn('_set_xtts_preload_ui_state(False, result=str(result))', MAIN)
        self.assertIn('if self._xtts_local_first_preloading:', MAIN)
        self.assertIn('Microphone ignored by XTTS preload UI gate', MAIN)

    def test_input_placeholder_api_supports_preload_message(self):
        self.assertIn('def set_input_enabled(self, enabled: bool, *, placeholder: str | None = None):', CHAT)
        self.assertIn('self.input_field.setPlaceholderText(str(placeholder))', CHAT)

    def test_local_first_gate_is_only_armed_for_explicit_cuda_prewarm(self):
        self.assertIn('settings.XTTS_LOCAL_FIRST_ENABLED', MAIN)
        self.assertIn('settings.XTTS_ALLOW_CUDA', MAIN)
        self.assertIn('str(settings.XTTS_DEVICE).strip().lower() == "cuda"', MAIN)
        self.assertIn('settings.AUDIO_BACKGROUND_XTTS_PREWARM', MAIN)


if __name__ == "__main__":
    unittest.main()
