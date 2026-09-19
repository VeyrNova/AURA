from regression_compat import assert_version_at_least
import array
import tempfile
import unittest
import wave
from pathlib import Path

from config.settings import settings
from voice.audio_postprocess import polish_wav_tail
from voice.text_to_speech import sanitize_for_speech
from voice.xtts_tts import XTTSTTS


class VoicePolishV0703Tests(unittest.TestCase):
    def test_version_and_continuous_playback_default(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.3")
        self.assertTrue(settings.FAST_SPEECH_CONTINUOUS_PLAYBACK)

    def test_weather_units_are_spoken_in_french(self):
        spoken = sanitize_for_speech(
            "Il fait 36.1 °C, ressenti 35.5 °C, humidité 29%, vent 12 km/h, 0.0 mm. Vérifiée à 13:15."
        )
        self.assertIn("36 virgule 1 degrés Celsius", spoken)
        self.assertIn("35 virgule 5 degrés Celsius", spoken)
        self.assertIn("29 pour cent", spoken)
        self.assertIn("12 kilomètres par heure", spoken)
        self.assertIn("0 virgule 0 millimètres", spoken)
        self.assertIn("13 heures 15", spoken)

    def test_h_and_degree_singular(self):
        spoken = sanitize_for_speech("Rappel à 1 h. Température 1 °C.")
        self.assertIn("1 heure", spoken)
        self.assertIn("1 degré Celsius", spoken)

    def test_weather_chunking_is_balanced(self):
        text = (
            "À Vidauban, Région PACA, France, il fait actuellement 36 virgule 1 degrés Celsius, "
            "ciel dégagé, ressenti 35 virgule 5 degrés Celsius, humidité 29 pour cent, "
            "vent 12 kilomètres par heure et précipitations 0 virgule 0 millimètres."
        )
        chunks = XTTSTTS._bounded_text_chunks(
            text, first_limit=72, next_limit=128, min_chars=36, max_chunks=8
        )
        self.assertGreater(len(chunks), 1)
        self.assertGreaterEqual(len(chunks[0]), 40)
        self.assertLessEqual(len(chunks[0]), 108)
        self.assertEqual(" ".join(chunks), text)

    def test_tail_polish_removes_post_silence_artifact(self):
        rate = 8000
        samples = array.array("h")
        # 200 ms of voice-like signal.
        for i in range(int(rate * 0.20)):
            samples.append(4500 if (i // 10) % 2 == 0 else -4500)
        # Genuine silence gap.
        samples.extend([0] * int(rate * 0.07))
        # Isolated end artifact/pop after the silence.
        samples.extend([12000] * int(rate * 0.012))

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tail.wav"
            with wave.open(str(path), "wb") as dst:
                dst.setnchannels(1)
                dst.setsampwidth(2)
                dst.setframerate(rate)
                dst.writeframes(samples.tobytes())
            before = path.stat().st_size
            self.assertTrue(polish_wav_tail(path, fade_ms=25, safety_silence_ms=30, silence_gap_ms=40))
            with wave.open(str(path), "rb") as src:
                payload = array.array("h")
                payload.frombytes(src.readframes(src.getnframes()))
            # Safety pad is silent and the late 12k pop is gone.
            self.assertTrue(all(v == 0 for v in payload[-int(rate * 0.02):]))
            self.assertLess(path.stat().st_size, before + int(rate * 0.1) * 2)


if __name__ == "__main__":
    unittest.main()
