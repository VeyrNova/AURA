import json
import unittest
from unittest.mock import patch

from ai.voice_brevity import concise_voice_handoff, cloud_voice_content_allowed
from config.settings import settings
from regression_compat import assert_version_at_least
from voice.elevenlabs_tts import ElevenLabsTTS
from voice.voice_profile import VoiceProfile


class _Response:
    def __init__(self, payload: bytes):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, *args):
        data, self.payload = self.payload, b""
        return data


class ConciseElevenLabsVoiceTests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.1.3.4")

    def test_long_visual_answer_becomes_short_handoff(self):
        text = "Une réponse très détaillée. " * 20
        spoken, changed = concise_voice_handoff(text)
        self.assertTrue(changed)
        self.assertLessEqual(len(spoken), settings.VOICE_CONCISE_MAX_CHARS)
        self.assertIn("affiche", spoken.casefold())

    def test_short_weather_style_answer_is_preserved(self):
        text = "À Marseille, 28 degrés et ciel dégagé. Pas de pluie prévue."
        spoken, changed = concise_voice_handoff(text)
        self.assertFalse(changed)
        self.assertEqual(spoken, text)

    def test_cloud_privacy_gate_blocks_secret_prompt(self):
        self.assertFalse(cloud_voice_content_allowed("Rappelle-moi mon mot de passe", "C'est affiché."))
        self.assertTrue(cloud_voice_content_allowed("Quelle météo à Nice ?", "À Nice, 27 degrés."))

    def test_profile_accepts_elevenlabs_and_keeps_piper_fallback(self):
        profile = VoiceProfile(
            engine="elevenlabs",
            fallback_engine="piper",
            elevenlabs_voice_id="voice-123",
            elevenlabs_voice_name="Aura Test",
        ).normalized()
        self.assertEqual(profile.engine, "elevenlabs")
        self.assertEqual(profile.fallback_engine, "piper")
        self.assertEqual(profile.elevenlabs_voice_id, "voice-123")

    def test_voice_list_uses_api_without_persisting_key(self):
        payload = json.dumps({"voices": [{"voice_id": "v1", "name": "Alice", "category": "premade"}]}).encode()
        ElevenLabsTTS._voices_cache = (0.0, ())
        with patch.object(settings, "ELEVENLABS_API_KEY", "secret-test-key"), \
             patch("voice.elevenlabs_tts.urllib.request.urlopen", return_value=_Response(payload)) as opener:
            voices = ElevenLabsTTS.list_voices(force_refresh=True)
        self.assertEqual(voices[0].voice_id, "v1")
        request = opener.call_args.args[0]
        self.assertNotIn("secret-test-key", request.full_url)

    def test_elevenlabs_is_unavailable_without_key(self):
        profile = VoiceProfile(engine="elevenlabs", elevenlabs_voice_id="v1").normalized()
        with patch.object(settings, "ELEVENLABS_ENABLED", True), patch.object(settings, "ELEVENLABS_API_KEY", ""):
            self.assertFalse(ElevenLabsTTS(profile).is_available())


    def test_included_quota_gate_refuses_overage_before_tts(self):
        with patch.object(settings, "ELEVENLABS_REQUIRE_QUOTA_CHECK", True), \
             patch.object(ElevenLabsTTS, "quota_status", return_value={
                 "character_count": 995, "character_limit": 1000, "current_overage": {"amount": "0"}
             }):
            with self.assertRaises(Exception):
                ElevenLabsTTS.ensure_included_quota(10)

    def test_included_quota_gate_accepts_remaining_allowance(self):
        with patch.object(settings, "ELEVENLABS_REQUIRE_QUOTA_CHECK", True), \
             patch.object(ElevenLabsTTS, "quota_status", return_value={
                 "character_count": 900, "character_limit": 1000, "current_overage": {"amount": "0"}
             }):
            result = ElevenLabsTTS.ensure_included_quota(50)
        self.assertEqual(result["character_limit"], 1000)

    def test_controlled_xtts_trial_default_is_off_in_new_voice_strategy(self):
        self.assertFalse(settings.XTTS_CONTROLLED_TRIAL_ENABLED)


if __name__ == "__main__":
    unittest.main()
