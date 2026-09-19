from regression_compat import assert_version_at_least
import unittest
from pathlib import Path

from config.settings import settings
from tools.models import ToolResult
from tools.weather import WeatherTool


ROOT = Path(__file__).resolve().parents[1]


class WeatherSpeechRoutingV07126Tests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.1.2.6")

    def test_dedicated_hud_preserves_speech_response(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        block = source[source.index("def _on_internet_tool_finished"):source.index("def _on_internet_tool_failed")]
        self.assertIn('if dedicated_shown:', block)
        self.assertIn('getattr(result, "speech_response", "")', block)
        self.assertNotIn('if dedicated_shown:\n            self._pending_voice_override = ""', block)

    def test_weather_result_can_keep_display_and_speech_separate(self):
        result = ToolResult(
            True,
            "À Ubud, il fait actuellement 29 °C. Humidité 80 %. Source : Open-Meteo.",
            "weather",
            "open-meteo",
            speech_response="À Ubud, 29 degrés, nuageux. Risque de pluie : 60 %.",
            data={"place_label": "Ubud", "temperature": 29},
        )
        self.assertNotEqual(result.response, result.speech_response)
        self.assertIn("Open-Meteo", result.response)
        self.assertNotIn("Open-Meteo", result.speech_response)
        self.assertLess(len(result.speech_response), len(result.response))

    def test_weather_concise_mode_enabled(self):
        self.assertTrue(settings.WEATHER_VOICE_CONCISE)


if __name__ == "__main__":
    unittest.main()
