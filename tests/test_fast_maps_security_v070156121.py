from regression_compat import assert_version_at_least
import unittest
from pathlib import Path

from config.settings import settings
from security.permissions import ACTION_POLICIES, DEFAULT_GRANTED_PERMISSIONS, Permission
from security.policy_engine import SecurityPolicyEngine
from security.risk import RiskLevel

ROOT = Path(__file__).resolve().parents[1]


class FastMapsSecurityHotfixTests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.15.6.12.1")

    def test_maps_read_only_actions_are_low_and_allowed(self):
        for action in ("MAPS_LOCATE", "MAPS_DIRECTIONS", "MAPS_OPEN_EXTERNAL"):
            policy = ACTION_POLICIES[action]
            self.assertEqual(policy.risk, RiskLevel.LOW)
            self.assertEqual(policy.permission, Permission.WEB_READ)
            decision = SecurityPolicyEngine().authorize(action)
            self.assertTrue(decision.allowed, (action, decision.reason))

    def test_current_location_is_separate_and_not_granted(self):
        self.assertNotIn(Permission.LOCATION_ACCESS, DEFAULT_GRANTED_PERMISSIONS)
        policy = ACTION_POLICIES["LOCATION_CURRENT"]
        self.assertEqual(policy.permission, Permission.LOCATION_ACCESS)
        self.assertEqual(policy.risk, RiskLevel.MEDIUM)
        decision = SecurityPolicyEngine().authorize("LOCATION_CURRENT", user_confirmed=True)
        self.assertFalse(decision.allowed)
        self.assertIn("location_access", decision.reason)

    def test_fast_mode_prewarms_small_model_and_keeps_it_hot(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("self._audio_test_mode = bool(settings.AUDIO_RUNTIME_PAUSED)", source)
        self.assertIn("FAST_TEXT_TEST_MODE: background fast brain prewarmed", source)
        self.assertIn("keep_alive=settings.FAST_TEXT_TEST_KEEP_ALIVE", source)
        self.assertIn('profile["keep_alive"] = settings.FAST_TEXT_TEST_KEEP_ALIVE', source)
        self.assertEqual(settings.FAST_TEXT_TEST_KEEP_ALIVE, "30m")

    def test_voice_status_is_consistently_paused_in_fast_mode(self):
        source = (ROOT / "voice" / "voice_engine.py").read_text(encoding="utf-8")
        self.assertIn("if self._runtime_paused:", source)
        self.assertIn('tts_engine="paused"', source)
        self.assertIn('input_ready=False', source)
        self.assertIn('output_ready=False', source)
        self.assertIn("set_runtime_paused", source)
        self.assertIn("TTS suspendu pendant le mode test rapide", source)
        self.assertIn("STT suspendu pendant le mode test rapide", source)

    def test_voice_runtime_pause_reports_disabled_capabilities(self):
        from voice.voice_engine import VoiceEngine
        engine = VoiceEngine()
        engine.set_runtime_paused(True)
        status = engine.status()
        self.assertFalse(status.enabled)
        self.assertFalse(status.input_ready)
        self.assertFalse(status.output_ready)
        self.assertEqual(status.tts_engine, "paused")


if __name__ == "__main__":
    unittest.main()
