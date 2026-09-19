from regression_compat import assert_version_at_least
import unittest
from unittest.mock import patch

from config.settings import settings
from runtime.resource_guardian import ResourceGuardian, ResourceSnapshot
from tools.weather import WeatherTool


class FakeVoice:
    def __init__(self, xtts=False):
        self.xtts = xtts
        self.xtts_releases = 0
        self.stt_releases = 0

    def xtts_model_loaded(self):
        return self.xtts

    def release_xtts_model(self):
        self.xtts_releases += 1
        was = self.xtts
        self.xtts = False
        return was

    def release_stt_model(self):
        self.stt_releases += 1
        return True


class FakeLLM:
    def __init__(self, resident=True):
        self.resident = resident
        self.unloads = []
        self.warmups = []

    def model_available(self, model):
        return True

    def running_model_info(self, model=None):
        if model and model.casefold() == settings.LLM_VOICE_MODEL.casefold() and self.resident:
            return {"name": model, "size": 4 * 1024**3, "size_vram": 2 * 1024**3}
        return None

    def running_model_query_ok(self):
        return True

    def unload_model(self, model):
        self.unloads.append(model)
        if model.casefold() == settings.LLM_VOICE_MODEL.casefold():
            self.resident = False
        return True

    def warmup(self, **kwargs):
        self.warmups.append(kwargs)
        self.resident = True
        return True


class FakeHTTPResponse:
    status_code = 200
    url = "https://api.open-meteo.com/v1/forecast"


class FakeHTTP:
    def __init__(self, payloads):
        self.payloads = list(payloads)

    def get_json(self, url):
        if "air-quality" in url:
            return ({"current": {}}, FakeHTTPResponse())
        return (self.payloads.pop(0), FakeHTTPResponse())


class VoiceResidencyWeatherV07125Tests(unittest.TestCase):
    @staticmethod
    def snap(ram=62.0, avail=5.9, vram_total=6141.0, ollama=2200.0):
        return ResourceSnapshot(
            ram_used_pct=ram,
            ram_total_gb=15.6,
            ram_available_gb=avail,
            vram_used_mb=ollama,
            vram_total_mb=vram_total,
            vram_used_pct=(100.0 * ollama / vram_total if vram_total else 0.0),
            gpu_name="RTX 4050 Laptop",
            ollama_vram_mb=ollama,
            ollama_model=settings.LLM_VOICE_MODEL,
        )

    def test_version_and_defaults(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.1.2.5")
        self.assertTrue(settings.VOICE_BRAIN_INDEPENDENT_RESIDENCY)
        self.assertEqual(settings.VOICE_BRAIN_INDEPENDENT_KEEP_ALIVE, "5m")
        self.assertTrue(settings.WEATHER_VOICE_CONCISE)

    def test_voice_profile_keeps_model_warm_when_cuda_xtts_is_display_blocked(self):
        llm = FakeLLM(resident=True)
        guardian = ResourceGuardian(llm, FakeVoice())
        with patch.object(guardian, "sample", return_value=self.snap()), patch.object(guardian, "_model_available", return_value=True):
            profile = guardian.llm_request_profile(voice_output=True, user_text="bonjour")
        self.assertFalse(profile["co_resident"])
        self.assertTrue(profile["independent_resident"])
        self.assertEqual(profile["keep_alive"], settings.VOICE_BRAIN_INDEPENDENT_KEEP_ALIVE)

    def test_tts_display_guard_preserves_warm_voice_brain_for_piper(self):
        llm = FakeLLM(resident=True)
        guardian = ResourceGuardian(llm, FakeVoice())
        guardian._last_llm_profile = {
            "name": "voice-fast", "provider": "local", "model": settings.LLM_VOICE_MODEL,
            "co_resident": False, "keep_alive": "0",
        }
        with patch.object(guardian, "sample", return_value=self.snap()), patch.object(guardian, "_running_info", return_value={"name": settings.LLM_VOICE_MODEL, "size": 4 * 1024**3, "size_vram": 2 * 1024**3}):
            decision = guardian.prepare_for_tts()
        self.assertEqual(decision.backend, "fallback")
        self.assertFalse(decision.ollama_unloaded)
        self.assertEqual(llm.unloads, [])
        self.assertTrue(guardian._last_llm_profile["independent_resident"])
        self.assertEqual(guardian._last_llm_profile["keep_alive"], settings.VOICE_BRAIN_INDEPENDENT_KEEP_ALIVE)

    def test_current_weather_spoken_is_short_and_source_free(self):
        fake = FakeHTTP([
            {"results": [{"name": "Paris", "admin1": "Île-de-France", "country": "France", "latitude": 48.85, "longitude": 2.35}]},
            {"current": {"temperature_2m": 24.2, "apparent_temperature": 24.8, "relative_humidity_2m": 52, "precipitation": 0.0, "weather_code": 1, "wind_speed_10m": 12.0},
             "daily": {"temperature_2m_max": [27], "temperature_2m_min": [18], "precipitation_probability_max": [15]}},
        ])
        result = WeatherTool(fake).execute("Paris")
        self.assertTrue(result.ok)
        self.assertIn("Open-Meteo", result.response)
        self.assertNotIn("Open-Meteo", result.speech_response)
        self.assertLessEqual(len(result.speech_response), 80)
        self.assertIn("Paris", result.speech_response)
        self.assertIn("24", result.speech_response)

    def test_tomorrow_weather_speaks_only_essentials_without_source(self):
        fake = FakeHTTP([
            {"results": [{"name": "Paris", "country": "France", "latitude": 48.85, "longitude": 2.35}]},
            {"daily": {"time": ["2026-08-10", "2026-08-11"], "weather_code": [1, 61], "temperature_2m_max": [27, 22], "temperature_2m_min": [18, 16], "precipitation_probability_max": [15, 70]}},
        ])
        result = WeatherTool(fake).execute("Paris", tomorrow=True)
        self.assertTrue(result.ok)
        self.assertNotIn("Open-Meteo", result.speech_response)
        self.assertIn("16 à 22", result.speech_response)
        self.assertIn("70%", result.speech_response)
        self.assertLessEqual(len(result.speech_response), 100)


if __name__ == "__main__":
    unittest.main()
