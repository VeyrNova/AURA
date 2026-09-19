import unittest
from unittest.mock import Mock, patch

from voice.errors import SpeechSynthesisUnavailableError
from voice.voice_profile import VoiceProfile
from voice.xtts_tts import XTTSTTS


class XTTSPresetResolutionTests(unittest.TestCase):
    def test_available_speakers_comes_from_loaded_model(self):
        api = Mock()
        api.speakers = ["Voice A", "Voice B"]
        tts = XTTSTTS(VoiceProfile(xtts_mode="preset", xtts_preset="Voice A"))
        with patch.object(tts, "_load_model", return_value=api):
            self.assertEqual(tts.available_speakers(), ("Voice A", "Voice B"))

    def test_valid_preset_is_passed_exactly(self):
        api = Mock()
        api.speakers = ["Voice A", "Voice B"]
        tts = XTTSTTS(VoiceProfile(xtts_mode="preset", xtts_preset="Voice B"))
        self.assertEqual(tts._speaker_kwargs(api), {"speaker": "Voice B"})

    def test_invalid_preset_fails_instead_of_silently_using_another_voice(self):
        api = Mock()
        api.speakers = ["Voice A", "Voice B"]
        tts = XTTSTTS(VoiceProfile(xtts_mode="preset", xtts_preset="Missing Voice"))
        # normalized() falls back on the static legacy default for an unknown preset;
        # force the runtime mismatch to emulate a different installed checkpoint.
        tts.profile.xtts_preset = "Missing Voice"
        with self.assertRaises(SpeechSynthesisUnavailableError):
            tts._speaker_kwargs(api)


if __name__ == "__main__":
    unittest.main()
