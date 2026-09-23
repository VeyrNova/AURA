import io
import json
import sys
import unittest
import urllib.error
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from config.settings import settings, valid_elevenlabs_api_key
from regression_compat import assert_version_at_least
from runtime.resource_guardian import ResourceGuardian
from voice.elevenlabs_tts import ElevenLabsTTS
from voice.errors import SpeechSynthesisUnavailableError
from voice.voice_profile import VoiceProfile


def _http_error(code, payload):
    return urllib.error.HTTPError(
        url="https://api.elevenlabs.io/v1/text-to-speech/test/stream",
        code=code,
        msg="error",
        hdrs=None,
        fp=io.BytesIO(json.dumps(payload).encode("utf-8")),
    )


class _DummyLLM:
    pass


class _DummyVoice:
    def __init__(self, engine="elevenlabs"):
        self.profile = SimpleNamespace(engine=engine)


class ElevenLabsCloudGuardV071345Tests(unittest.TestCase):
    def setUp(self):
        self.old_key = settings.ELEVENLABS_API_KEY
        self.old_enabled = settings.ELEVENLABS_ENABLED
        settings.ELEVENLABS_API_KEY = "sk_test-secret-key-123456789"
        settings.ELEVENLABS_ENABLED = True
        ElevenLabsTTS._quota_cache = (123.0, {"character_count": 0, "character_limit": 10000})

    def tearDown(self):
        settings.ELEVENLABS_API_KEY = self.old_key
        settings.ELEVENLABS_ENABLED = self.old_enabled
        ElevenLabsTTS._quota_cache = (0.0, {})

    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.1.3.4.5")

    def test_key_validator_requires_secret_sk_prefix(self):
        self.assertFalse(valid_elevenlabs_api_key("1234567890abcdef"))
        self.assertFalse(valid_elevenlabs_api_key("api-key-id-123456789"))
        self.assertTrue(valid_elevenlabs_api_key("sk_secret-1234567890"))

    def test_tts_402_surfaces_provider_detail_and_invalidates_quota_cache(self):
        profile = VoiceProfile(
            engine="elevenlabs",
            fallback_engine="piper",
            elevenlabs_voice_id="voice-test",
            elevenlabs_model="eleven_flash_v2_5",
        ).normalized()
        backend = ElevenLabsTTS(profile)
        err = _http_error(402, {"detail": {"type": "payment_required", "code": "quota_exceeded", "message": "Insufficient credits"}})
        fake_sd = MagicMock()
        with patch.dict(sys.modules, {"sounddevice": fake_sd}), \
             patch.object(ElevenLabsTTS, "ensure_included_quota", return_value={"character_count": 0, "character_limit": 10000}), \
             patch("voice.elevenlabs_tts.urllib.request.urlopen", side_effect=err):
            with self.assertRaises(SpeechSynthesisUnavailableError) as ctx:
                backend.speak("Bonjour Aura")
        msg = str(ctx.exception)
        self.assertIn("HTTP 402", msg)
        self.assertIn("Insufficient credits", msg)
        self.assertEqual(ElevenLabsTTS._quota_cache, (0.0, {}))

    def test_guardian_skips_xtts_and_voice_brain_prewarm_for_cloud_voice(self):
        guardian = ResourceGuardian(_DummyLLM(), _DummyVoice("elevenlabs"))
        self.assertFalse(guardian.conditional_xtts_prewarm())
        self.assertEqual(guardian._xtts_prewarm_last_result, "cloud-voice")
        self.assertFalse(guardian.conditional_voice_llm_prewarm())
        self.assertEqual(guardian._voice_llm_prewarm_last_result, "cloud-voice")

    def test_ui_workers_skip_heavy_cloud_prewarm_but_keep_piper(self):
        source = (settings.BASE_DIR / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("Cloud voice optimization: XTTS prewarm skipped engine=elevenlabs fallback=piper", source)
        self.assertIn("Cloud voice optimization: Voice Brain startup prewarm skipped engine=elevenlabs", source)

    def test_dialog_explains_secret_key_vs_key_id(self):
        source = (settings.BASE_DIR / "ui" / "voice_settings_dialog.py").read_text(encoding="utf-8")
        self.assertIn("commençant par 'sk_'", source)
        self.assertIn("identifiant de clé", source)


if __name__ == "__main__":
    unittest.main()
