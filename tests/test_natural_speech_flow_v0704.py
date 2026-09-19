from regression_compat import assert_version_at_least
import unittest

from config.settings import settings
from voice.text_to_speech import sanitize_for_speech
from voice.xtts_tts import XTTSTTS
from tools.weather import WeatherTool
from tools.safe_http import HTTPResponse
import json


class FakeHTTP:
    def __init__(self, payloads):
        self.payloads = list(payloads)

    def get_json(self, url, headers=None):
        payload = self.payloads.pop(0)
        return payload, HTTPResponse(url, 200, "application/json", json.dumps(payload).encode())


class NaturalSpeechFlowV0704Tests(unittest.TestCase):
    def test_version_and_smoother_defaults(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.4")
        self.assertGreaterEqual(settings.FAST_SPEECH_FIRST_CHUNK_CHARS, 110)
        self.assertGreaterEqual(settings.FAST_SPEECH_NEXT_CHUNK_CHARS, 160)
        self.assertGreaterEqual(settings.FAST_SPEECH_MIN_CHUNK_CHARS, 44)

    def test_log_example_never_splits_humidity_phrase(self):
        text = (
            "C'est un jour chaud ! Avec une température de 36,1 degrés Celsius et une humidité "
            "relativement faible, cela pourrait être un peu agaçant pour certaines personnes. "
            "Il est peut-être utile d'apporter de l'eau ou des ombres pour se protéger du soleil."
        )
        plan = XTTSTTS._natural_chunk_plan(
            text, first_limit=120, next_limit=170, min_chars=48, max_chunks=8
        )
        chunks = tuple(item.text for item in plan)
        self.assertEqual(" ".join(chunks), text)
        self.assertFalse(any(chunk.rstrip().endswith("une humidité") for chunk in chunks))
        self.assertIn("une humidité relativement faible", chunks[0])
        self.assertEqual(plan[0].boundary, "sentence")

    def test_complete_sentences_are_prioritized(self):
        text = (
            "Première phrase complète et naturelle pour AURA. "
            "Deuxième phrase complète, assez longue pour conserver une intonation cohérente. "
            "Troisième phrase courte."
        )
        plan = XTTSTTS._natural_chunk_plan(
            text, first_limit=90, next_limit=120, min_chars=40, max_chunks=8
        )
        self.assertTrue(all(item.boundary in {"sentence", "final"} for item in plan))
        self.assertEqual(" ".join(item.text for item in plan), text)

    def test_long_sentence_uses_clause_before_whitespace(self):
        text = (
            "Cette phrase est volontairement longue afin de tester la voix naturelle d'AURA, "
            "mais elle contient une vraie séparation grammaticale qui doit être préférée à une coupure arbitraire dans un groupe de mots."
        )
        plan = XTTSTTS._natural_chunk_plan(
            text, first_limit=95, next_limit=140, min_chars=42, max_chunks=8
        )
        self.assertEqual(" ".join(item.text for item in plan), text)
        self.assertEqual(plan[0].boundary, "clause")
        self.assertTrue(plan[0].text.endswith(","))

    def test_fallback_does_not_end_on_determiner(self):
        text = " ".join(["AURA"] * 18 + ["avec", "une", "voix", "vraiment", "plus", "naturelle"] + ["continue"] * 20)
        plan = XTTSTTS._natural_chunk_plan(
            text, first_limit=80, next_limit=100, min_chars=35, max_chunks=8
        )
        forbidden = XTTSTTS._FORBIDDEN_FALLBACK_ENDINGS
        for item in plan[:-1]:
            last = item.text.rstrip(".,;:!? ").split()[-1].lower()
            if item.boundary == "fallback":
                self.assertNotIn(last, forbidden)

    def test_tiny_final_sentence_is_not_orphaned(self):
        text = (
            "Cette première partie est assez longue pour approcher la cible de découpage naturel sans être cassée au milieu. "
            "Tout va bien. "
            "À bientôt."
        )
        plan = XTTSTTS._natural_chunk_plan(
            text, first_limit=90, next_limit=120, min_chars=40, max_chunks=8
        )
        self.assertEqual(" ".join(item.text for item in plan), text)
        self.assertGreaterEqual(len(plan[-1].text), 20)
        self.assertLess(len(plan[0].text), len(text))

    def test_weather_answer_is_sentence_shaped(self):
        fake = FakeHTTP([
            {"results": [{"name": "Paris", "admin1": "Île-de-France", "country": "France", "latitude": 48.85, "longitude": 2.35}]},
            {"current": {"temperature_2m": 28.2, "apparent_temperature": 29.1, "relative_humidity_2m": 28, "precipitation": 0.0, "weather_code": 0, "wind_speed_10m": 4.0}},
        ])
        result = WeatherTool(fake).execute("Paris")
        self.assertTrue(result.ok)
        self.assertIn("Conditions actuelles : ciel dégagé.", result.response)
        self.assertIn("Le ressenti est de 29.1 °C.", result.response)
        self.assertIn("L'humidité est de 28%", result.response)
        self.assertIn("Les précipitations actuelles sont de 0.0 mm.", result.response)
        self.assertGreaterEqual(result.response.count("."), 5)

    def test_spoken_weather_keeps_natural_units(self):
        spoken = sanitize_for_speech(
            "Le ressenti est de 29.1 °C. L'humidité est de 28%, et le vent souffle à 4 km/h."
        )
        self.assertIn("29 virgule 1 degrés Celsius", spoken)
        self.assertIn("28 pour cent", spoken)
        self.assertIn("4 kilomètres par heure", spoken)


if __name__ == "__main__":
    unittest.main()
