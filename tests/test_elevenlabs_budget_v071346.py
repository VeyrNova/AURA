import unittest
from unittest.mock import patch

from ai.voice_brevity import concise_voice_handoff
from config.settings import settings
from regression_compat import assert_version_at_least
from voice.elevenlabs_tts import ElevenLabsTTS
from voice.errors import SpeechSynthesisUnavailableError


class ElevenLabsBudgetV071346Tests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.1.3.4.6")

    def test_cloud_handoff_is_shorter_than_generic_voice_handoff(self):
        text = "Une réponse très détaillée. " * 20
        spoken, changed = concise_voice_handoff(
            text,
            max_chars=settings.ELEVENLABS_MAX_SPEECH_CHARS,
            long_reply=settings.ELEVENLABS_LONG_REPLY,
        )
        self.assertTrue(changed)
        self.assertEqual(spoken, "Je t'affiche le détail à l'écran.")
        self.assertLessEqual(len(spoken), 40)

    def test_normal_budget_accepts_short_cloud_phrase(self):
        with patch.object(settings, "ELEVENLABS_REQUIRE_QUOTA_CHECK", True), \
             patch.object(ElevenLabsTTS, "quota_status", return_value={
                 "character_count": 208,
                 "character_limit": 10000,
                 "current_overage": {"amount": "0"},
                 "status": "active",
                 "has_open_invoices": False,
             }):
            result = ElevenLabsTTS.ensure_included_quota(52)
        self.assertEqual(result["character_count"], 208)

    def test_low_budget_accepts_compact_handoff(self):
        with patch.object(settings, "ELEVENLABS_REQUIRE_QUOTA_CHECK", True), \
             patch.object(settings, "ELEVENLABS_LOW_QUOTA_RATIO", 0.25), \
             patch.object(settings, "ELEVENLABS_CRITICAL_QUOTA_RATIO", 0.05), \
             patch.object(settings, "ELEVENLABS_LOW_QUOTA_MAX_CHARS", 55), \
             patch.object(ElevenLabsTTS, "quota_status", return_value={
                 "character_count": 8000,
                 "character_limit": 10000,
                 "current_overage": {"amount": "0"},
                 "status": "active",
                 "has_open_invoices": False,
             }):
            result = ElevenLabsTTS.ensure_included_quota(33)
        self.assertEqual(result["character_limit"], 10000)

    def test_low_budget_routes_longer_phrase_local(self):
        with patch.object(settings, "ELEVENLABS_REQUIRE_QUOTA_CHECK", True), \
             patch.object(settings, "ELEVENLABS_LOW_QUOTA_RATIO", 0.25), \
             patch.object(settings, "ELEVENLABS_CRITICAL_QUOTA_RATIO", 0.05), \
             patch.object(settings, "ELEVENLABS_LOW_QUOTA_MAX_CHARS", 55), \
             patch.object(ElevenLabsTTS, "quota_status", return_value={
                 "character_count": 8000,
                 "character_limit": 10000,
                 "current_overage": {"amount": "0"},
                 "status": "active",
                 "has_open_invoices": False,
             }):
            with self.assertRaises(SpeechSynthesisUnavailableError) as ctx:
                ElevenLabsTTS.ensure_included_quota(70)
        self.assertIn("Budget ElevenLabs bas", str(ctx.exception))

    def test_critical_budget_routes_everything_local(self):
        with patch.object(settings, "ELEVENLABS_REQUIRE_QUOTA_CHECK", True), \
             patch.object(settings, "ELEVENLABS_LOW_QUOTA_RATIO", 0.25), \
             patch.object(settings, "ELEVENLABS_CRITICAL_QUOTA_RATIO", 0.05), \
             patch.object(ElevenLabsTTS, "quota_status", return_value={
                 "character_count": 9500,
                 "character_limit": 10000,
                 "current_overage": {"amount": "0"},
                 "status": "active",
                 "has_open_invoices": False,
             }):
            with self.assertRaises(SpeechSynthesisUnavailableError) as ctx:
                ElevenLabsTTS.ensure_included_quota(20)
        self.assertIn("Budget ElevenLabs critique", str(ctx.exception))

    def test_ui_uses_cloud_specific_concise_budget(self):
        source = (settings.BASE_DIR / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("settings.ELEVENLABS_LONG_REPLY if cloud_voice else None", source)
        self.assertIn("settings.ELEVENLABS_MAX_SPEECH_CHARS", source)


if __name__ == "__main__":
    unittest.main()
