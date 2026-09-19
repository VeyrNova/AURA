from regression_compat import assert_version_at_least
import json
import unittest
from pathlib import Path

from ai.speech_quality import deterministic_french_fallback, find_voice_quality_issues
from ai.voice_brevity import voice_brevity_policy, voice_output_contract
from config.settings import settings
from tools.models import ToolResult
from tools.safe_http import HTTPResponse
from tools.weather import WeatherTool


class FakeHTTP:
    def __init__(self, payloads):
        self.payloads = list(payloads)

    def get_json(self, url, headers=None):
        payload = self.payloads.pop(0)
        return payload, HTTPResponse(url, 200, "application/json", json.dumps(payload).encode())


class RuntimeFrenchIntegrityV07013Tests(unittest.TestCase):
    def test_version_and_runtime_defaults(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.13")
        self.assertEqual(settings.RESOURCE_XTTS_IDLE_SECONDS, 300.0)
        self.assertEqual(settings.VOICE_BRAIN_PREWARM_DELAY_MS, 1800)
        self.assertEqual(settings.VOICE_BRAIN_PREWARM_MAX_RAM_PCT, 93.0)
        self.assertEqual(settings.VOICE_BRAIN_PREWARM_MIN_AVAILABLE_RAM_GB, 1.15)

    def test_bad_m_y_assurer_is_detected_and_fixed(self):
        bad = "Je vais m'y assurer d'être plus précis dans le futur."
        codes = {issue.code for issue in find_voice_quality_issues(bad)}
        self.assertIn("bad_pronoun_y_assurer", codes)
        fixed = deterministic_french_fallback(bad)
        self.assertEqual(fixed, "Je vais m'assurer d'être plus précis dans le futur.")
        self.assertEqual(find_voice_quality_issues(fixed), ())

    def test_me_aider_is_detected_and_fixed(self):
        bad = "Voici quelques façons dont vous pourriez me aider."
        codes = {issue.code for issue in find_voice_quality_issues(bad)}
        self.assertIn("missing_elision_me_aider", codes)
        fixed = deterministic_french_fallback(bad)
        self.assertIn("m'aider", fixed)
        self.assertEqual(find_voice_quality_issues(fixed), ())

    def test_other_high_confidence_elisions_are_fixed(self):
        bad = "Tu peux te aider et se assurer de être prêt."
        fixed = deterministic_french_fallback(bad)
        self.assertEqual(fixed, "Tu peux t'aider et s'assurer d'être prêt.")
        self.assertEqual(find_voice_quality_issues(fixed), ())

    def test_voice_contract_explicitly_requires_french_elisions(self):
        contract = voice_output_contract(voice_brevity_policy("Bonjour Aura"))
        self.assertIn("VOICE OUTPUT CONTRACT v0.7.0.14", contract)
        self.assertIn("m'aider", contract)
        self.assertIn("s'assurer", contract)
        self.assertIn("d'être", contract)

    def test_tool_result_keeps_backward_compatible_optional_speech_response(self):
        result = ToolResult(True, "Affichage complet", "weather", "open-meteo")
        self.assertEqual(result.speech_response, "")

    def test_current_weather_has_rich_display_and_concise_voice(self):
        fake = FakeHTTP([
            {"results": [{"name": "Vidauban", "admin1": "Région PACA", "country": "France", "latitude": 43.43, "longitude": 6.43}]},
            {"current": {"temperature_2m": 33.1, "apparent_temperature": 33.2, "relative_humidity_2m": 38, "precipitation": 0.0, "weather_code": 0, "wind_speed_10m": 12.0}},
        ])
        result = WeatherTool(fake).execute("Vidauban")
        self.assertTrue(result.ok)
        self.assertIn("Région PACA, France", result.response)
        self.assertIn("Source : Open-Meteo", result.response)
        self.assertTrue(result.speech_response)
        self.assertIn("À Vidauban", result.speech_response)
        self.assertIn("Pas de pluie actuellement", result.speech_response)
        self.assertNotIn("Source :", result.speech_response)
        self.assertLess(len(result.speech_response), 220)
        self.assertLess(len(result.speech_response), len(result.response))

    def test_tomorrow_weather_has_concise_voice(self):
        fake = FakeHTTP([
            {"results": [{"name": "Vidauban", "country": "France", "latitude": 43.43, "longitude": 6.43}]},
            {"daily": {"time": ["2026-08-08", "2026-08-09"], "weather_code": [0, 61], "temperature_2m_max": [33, 28], "temperature_2m_min": [20, 19], "precipitation_probability_max": [0, 70]}},
        ])
        result = WeatherTool(fake).execute("Vidauban", tomorrow=True)
        self.assertTrue(result.ok)
        self.assertIn("Prévision vérifiée", result.response)
        self.assertIn("Risque de pluie : 70%", result.speech_response)
        self.assertNotIn("Open-Meteo", result.speech_response)
        self.assertLess(len(result.speech_response), 190)

    def test_core_banner_uses_dynamic_app_version(self):
        source = (Path(__file__).resolve().parents[1] / "core" / "aura_core.py").read_text(encoding="utf-8")
        self.assertIn("{settings.APP_VERSION}", source)
        self.assertNotIn("Pixel Match UI Shell 0.7.0.11", source)

    def test_main_window_consumes_tool_voice_override(self):
        source = (Path(__file__).resolve().parents[1] / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("_pending_voice_override", source)
        self.assertIn("TTS concise tool override", source)
        self.assertIn('getattr(result, "speech_response", "")', source)

    def test_known_french_fix_is_attempted_before_llm_correction(self):
        source = (Path(__file__).resolve().parents[1] / "ui" / "main_window.py").read_text(encoding="utf-8")
        fallback_pos = source.index("fallback = deterministic_french_fallback(original_sentence)")
        llm_pos = source.index("quality_correction_messages(original_sentence)")
        self.assertLess(fallback_pos, llm_pos)


if __name__ == "__main__":
    unittest.main()
