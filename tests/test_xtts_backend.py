import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voice.voice_profile import VoiceProfile
from voice.xtts_tts import XTTSTTS


class XTTSBackendTests(unittest.TestCase):
    def test_preset_mode_does_not_require_reference(self):
        tts = XTTSTTS(VoiceProfile(xtts_mode="preset", xtts_preset="Ana Florence"))
        self.assertTrue(tts.reference_ready())
        self.assertIn("Ana Florence", tts.voice_label)

    def test_custom_mode_requires_reference(self):
        tts = XTTSTTS(VoiceProfile(xtts_mode="custom", xtts_reference_wav=""))
        self.assertFalse(tts.reference_ready())

    def test_custom_mode_accepts_existing_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "ref.wav"
            ref.write_bytes(b"x")
            tts = XTTSTTS(VoiceProfile(xtts_mode="custom", xtts_reference_wav=str(ref)))
            self.assertTrue(tts.reference_ready())

    def test_custom_voice_is_cached_after_first_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            ref = Path(tmp) / "ref.wav"
            ref.write_bytes(b"x")
            tts = XTTSTTS(VoiceProfile(xtts_mode="custom", xtts_reference_wav=str(ref), xtts_speaker_id="AURA_CUSTOM"))
            first = tts._speaker_kwargs()
            self.assertIn("speaker_wav", first)
            tts._custom_cached = True
            second = tts._speaker_kwargs()
            self.assertNotIn("speaker_wav", second)
            self.assertEqual(second["speaker"], "AURA_CUSTOM")

    def test_model_ready_accepts_complete_real_coqui_cache_without_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "tts_models--multilingual--multi-dataset--xtts_v2"
            cache.mkdir()
            for name in XTTSTTS.REQUIRED_MODEL_FILES:
                (cache / name).write_bytes(b"x")
            tts = XTTSTTS(VoiceProfile())
            with patch.object(XTTSTTS, "model_cache_candidates", return_value=(cache,)):
                self.assertTrue(tts.model_ready())
                self.assertEqual(XTTSTTS.model_cache_dir(), cache)

    def test_model_ready_rejects_incomplete_cache_even_with_legacy_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = root / "tts_models--multilingual--multi-dataset--xtts_v2"
            cache.mkdir()
            (cache / "speakers_xtts.pth").write_bytes(b"x")
            marker = root / ".installed"
            marker.write_text("legacy", encoding="utf-8")
            tts = XTTSTTS(VoiceProfile())
            with patch.object(XTTSTTS, "model_cache_candidates", return_value=(cache,)), \
                 patch.object(tts, "install_marker", return_value=marker):
                self.assertFalse(tts.model_ready())


if __name__ == "__main__":
    unittest.main()
