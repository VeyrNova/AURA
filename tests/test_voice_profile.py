import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from voice.voice_profile import VoiceProfile, VoiceProfileStore, XTTS_FEMALE_PRESETS


class VoiceProfileTests(unittest.TestCase):
    def test_default_profile_prefers_xtts_with_piper_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = VoiceProfileStore(Path(tmp) / "voice_profile.json")
            profile = store.load()
        self.assertEqual(profile.engine, "xtts")
        self.assertEqual(profile.fallback_engine, "piper")
        self.assertIn(profile.xtts_preset, XTTS_FEMALE_PRESETS)

    def test_profile_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = VoiceProfileStore(Path(tmp) / "voice_profile.json")
            expected = VoiceProfile(xtts_preset="Sofia Hellen", xtts_speed=0.93, xtts_temperature=0.72)
            store.save(expected)
            actual = store.load()
        self.assertEqual(actual.xtts_preset, "Sofia Hellen")
        self.assertAlmostEqual(actual.xtts_speed, 0.93)
        self.assertAlmostEqual(actual.xtts_temperature, 0.72)

    def test_invalid_values_are_bounded(self):
        profile = VoiceProfile(engine="bad", xtts_mode="bad", xtts_speed=9, xtts_temperature=0.1).normalized()
        self.assertEqual(profile.engine, "xtts")
        self.assertEqual(profile.xtts_mode, "preset")
        self.assertEqual(profile.xtts_speed, 1.10)
        self.assertEqual(profile.xtts_temperature, 0.45)

    def test_import_reference_copies_valid_wav(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src.wav"
            with wave.open(str(src), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(b"\x00\x00" * 16000)
            store = VoiceProfileStore(root / "config" / "voice_profile.json")
            store.reference_dir = root / "refs"
            store.reference_dir.mkdir()
            dst = store.import_reference(src)
            self.assertTrue(dst.is_file())
            self.assertEqual(dst.name, "aura_reference.wav")

    def test_import_reference_rejects_non_wav(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "voice.mp3"
            src.write_bytes(b"not audio")
            store = VoiceProfileStore(root / "voice_profile.json")
            with self.assertRaises(ValueError):
                store.import_reference(src)

    def test_runtime_xtts_speaker_name_is_preserved(self):
        profile = VoiceProfile(xtts_preset="Runtime Speaker 42").normalized()
        self.assertEqual(profile.xtts_preset, "Runtime Speaker 42")


if __name__ == "__main__":
    unittest.main()
