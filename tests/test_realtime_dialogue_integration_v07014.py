from regression_compat import assert_version_at_least
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from config.settings import settings
from runtime.resource_guardian import ResourceGuardian, ResourcePressureError, ResourceSnapshot
from tools.internet_manager import InternetToolManager
from tools.safe_http import HTTPResponse
from tools.weather import WeatherTool

ROOT = Path(__file__).resolve().parents[1]


class FakeVoice:
    def __init__(self, loaded=True):
        self.loaded = loaded
        self.stt_releases = 0

    def xtts_model_loaded(self):
        return self.loaded

    def release_stt_model(self):
        self.stt_releases += 1
        return True


class FakeLLM:
    pass


class FakeHTTP:
    def __init__(self, payloads):
        self.payloads = list(payloads)

    def get_json(self, url, headers=None):
        payload = self.payloads.pop(0)
        return payload, HTTPResponse(url, 200, "application/json", json.dumps(payload).encode())


class RealtimeDialogueIntegrationV07014Tests(unittest.TestCase):
    @staticmethod
    def snap(ram=84.0, vram_used=2000.0):
        return ResourceSnapshot(
            ram_used_pct=float(ram),
            ram_total_gb=15.6,
            ram_available_gb=max(0.2, 15.6 * (100.0 - float(ram)) / 100.0),
            vram_used_mb=float(vram_used),
            vram_total_mb=6141.0,
            vram_used_pct=100.0 * float(vram_used) / 6141.0,
            gpu_name="RTX Test",
            ollama_vram_mb=0.0,
            ollama_model=settings.LLM_VOICE_MODEL,
        )

    def test_version_and_realtime_defaults(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.14")
        self.assertTrue(settings.REALTIME_DIALOGUE_ENABLED)
        self.assertTrue(settings.REALTIME_DIALOGUE_REQUIRE_CORESIDENCE)
        self.assertLess(settings.REALTIME_DIALOGUE_MAX_RAM_PCT, settings.RESOURCE_RAM_CRITICAL_PCT)

    def test_guardian_allows_hot_safe_coresidence_without_unload(self):
        voice = FakeVoice(loaded=True)
        guardian = ResourceGuardian(FakeLLM(), voice)
        profile = {"name": "voice-fast", "model": settings.LLM_VOICE_MODEL, "co_resident": True}
        guardian._last_llm_profile = dict(profile)
        with patch.object(guardian, "dual_brain_co_resident_ready", return_value=True), \
             patch.object(settings, "OPENGL_ORB_ENABLED", False), patch.object(
            guardian, "sample", return_value=self.snap(ram=84.0, vram_used=2000.0)
        ):
            self.assertTrue(guardian.realtime_dialogue_ready(profile))
            decision = guardian.prepare_for_realtime_tts(profile)
        self.assertEqual(decision.backend, "xtts")
        self.assertFalse(decision.ollama_unloaded)
        self.assertEqual(voice.stt_releases, 1)

    def test_guardian_fails_closed_instead_of_unloading_llm(self):
        voice = FakeVoice(loaded=True)
        guardian = ResourceGuardian(FakeLLM(), voice)
        profile = {"name": "voice-fast", "model": settings.LLM_VOICE_MODEL, "co_resident": True}
        guardian._last_llm_profile = dict(profile)
        with patch.object(guardian, "dual_brain_co_resident_ready", return_value=True), patch.object(
            guardian, "sample", return_value=self.snap(ram=settings.REALTIME_DIALOGUE_MAX_RAM_PCT + 0.1)
        ):
            with self.assertRaises(ResourcePressureError):
                guardian.prepare_for_realtime_tts(profile)

    def test_voice_turn_streams_text_and_has_sentence_queue(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("speech_segment = Signal(str)", source)
        self.assertIn("RealtimeSentenceBuffer()", source)
        self.assertIn("self.partial.emit(chunk)", source)
        self.assertIn("class RealtimeTTSWorker", source)
        self.assertIn("prepare_for_realtime_tts", source)
        self.assertIn("Realtime dialogue final TTS event consumed", source)

    def test_final_corrected_text_replaces_raw_stream(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        chat = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
        self.assertIn("self.chat_panel.set_aura_stream_text(reply)", source)
        self.assertIn("def set_aura_stream_text", chat)

    def test_implicit_local_weather_is_not_geocoded_as_literal_city(self):
        for text in (
            "Quel temps fait-il sur ma position locale ?",
            "Météo sur ma position locale ?",
            "Météo chez moi ?",
        ):
            self.assertEqual(InternetToolManager._extract_weather_location(text), "")
        self.assertEqual(InternetToolManager._extract_weather_location("Météo à Vidauban ?"), "Vidauban")

    def test_current_weather_spoken_form_is_under_120_chars(self):
        fake = FakeHTTP([
            {"results": [{"name": "Vidauban", "admin1": "Région PACA", "country": "France", "latitude": 43.43, "longitude": 6.43}]},
            {"current": {"temperature_2m": 32.8, "apparent_temperature": 33.1, "relative_humidity_2m": 39, "precipitation": 0.0, "weather_code": 0, "wind_speed_10m": 11.0}},
        ])
        result = WeatherTool(fake).execute("Vidauban")
        self.assertTrue(result.ok)
        self.assertIn("L'humidité est de 39%", result.response)
        self.assertLessEqual(len(result.speech_response), 120)
        self.assertNotIn("Vent 11 kilomètres par heure", result.speech_response)
        self.assertIn("Pas de pluie actuellement", result.speech_response)
        self.assertNotIn("humidité", result.speech_response.casefold())
        self.assertNotIn("Open-Meteo", result.speech_response)


if __name__ == "__main__":
    unittest.main()
