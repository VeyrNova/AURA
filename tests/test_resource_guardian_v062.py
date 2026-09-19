import unittest
from unittest.mock import MagicMock, patch

from ai.llm_manager import OllamaProvider
from config.settings import settings
from runtime.resource_guardian import (
    ResourceGuardian,
    ResourcePressureError,
    ResourceSnapshot,
)


class FakeLLM:
    def __init__(self, *, unload_ok=True, running=None):
        self.unload_ok = unload_ok
        self.running = running
        self.unload_calls = 0

    def unload(self):
        self.unload_calls += 1
        return self.unload_ok

    def running_model_info(self):
        return self.running


class FakeVoice:
    def __init__(self):
        self.xtts_releases = 0
        self.stt_releases = 0
        self.xtts_loaded = True

    def release_xtts_model(self):
        self.xtts_releases += 1
        was = self.xtts_loaded
        self.xtts_loaded = False
        return was

    def release_stt_model(self):
        self.stt_releases += 1
        return True

    def xtts_model_loaded(self):
        return self.xtts_loaded

    def release_heavy_models(self):
        self.release_xtts_model()
        self.release_stt_model()


class ResourceGuardianTests(unittest.TestCase):
    @staticmethod
    def snap(ram=50.0, vram=20.0, ollama=0.0):
        return ResourceSnapshot(
            ram_used_pct=ram,
            ram_total_gb=16.0,
            ram_available_gb=8.0,
            vram_used_mb=vram * 61.44,
            vram_total_mb=6144.0,
            vram_used_pct=vram,
            gpu_name="RTX Test",
            ollama_vram_mb=ollama,
            ollama_model="llama" if ollama else "",
        )

    def test_prepare_for_llm_releases_voice_models(self):
        voice = FakeVoice()
        guardian = ResourceGuardian(FakeLLM(), voice)
        with patch.object(guardian, "sample", return_value=self.snap(ram=81)):
            snapshot = guardian.prepare_for_llm()
        self.assertEqual(snapshot.ram_used_pct, 81)
        self.assertEqual(voice.xtts_releases, 1)
        self.assertEqual(voice.stt_releases, 1)

    def test_prepare_for_llm_blocks_emergency_ram(self):
        voice = FakeVoice()
        guardian = ResourceGuardian(FakeLLM(), voice)
        with patch.object(guardian, "sample", return_value=self.snap(ram=settings.RESOURCE_RAM_EMERGENCY_PCT + 1)):
            with self.assertRaises(ResourcePressureError):
                guardian.prepare_for_llm()
        self.assertEqual(voice.xtts_releases, 1)

    def test_prepare_for_tts_unloads_ollama_before_xtts(self):
        llm = FakeLLM(unload_ok=True, running={"name": "llama", "size_vram": 5 * 1024**3})
        voice = FakeVoice()
        guardian = ResourceGuardian(llm, voice)
        with patch.object(guardian, "_wait_ollama_unloaded", return_value=True), \
             patch.object(guardian, "sample", return_value=self.snap(ram=81, vram=30, ollama=0)), \
             patch("runtime.resource_guardian.settings.XTTS_DEVICE", "cpu"):
            decision = guardian.prepare_for_tts()
        self.assertEqual(llm.unload_calls, 1)
        self.assertEqual(decision.backend, "xtts")
        self.assertTrue(decision.ollama_unloaded)

    def test_prepare_for_tts_falls_back_if_ollama_did_not_unload(self):
        llm = FakeLLM(unload_ok=False, running={"name": "llama", "size_vram": 5 * 1024**3})
        voice = FakeVoice()
        guardian = ResourceGuardian(llm, voice)
        with patch.object(guardian, "sample", return_value=self.snap(ram=81, vram=90, ollama=5120)):
            decision = guardian.prepare_for_tts()
        self.assertEqual(decision.backend, "fallback")
        self.assertGreaterEqual(voice.xtts_releases, 1)

    def test_prepare_for_tts_falls_back_on_critical_ram(self):
        llm = FakeLLM(unload_ok=True, running=None)
        voice = FakeVoice()
        guardian = ResourceGuardian(llm, voice)
        with patch.object(guardian, "sample", return_value=self.snap(ram=settings.RESOURCE_RAM_CRITICAL_PCT)):
            decision = guardian.prepare_for_tts()
        self.assertEqual(decision.backend, "fallback")
        self.assertIn("RAM", decision.reason)

    def test_strict_xtts_test_is_blocked_instead_of_falling_back(self):
        llm = FakeLLM(unload_ok=False, running={"name": "llama", "size_vram": 5 * 1024**3})
        voice = FakeVoice()
        guardian = ResourceGuardian(llm, voice)
        with patch.object(guardian, "sample", return_value=self.snap(ram=80, vram=90, ollama=5120)):
            with self.assertRaises(ResourcePressureError):
                guardian.prepare_for_tts(strict_test=True)

    def test_after_stt_releases_whisper_by_default(self):
        voice = FakeVoice()
        guardian = ResourceGuardian(FakeLLM(), voice)
        guardian.after_stt()
        self.assertEqual(voice.stt_releases, 1)

    def test_idle_maintenance_releases_xtts_after_timeout(self):
        voice = FakeVoice()
        now = [1.0 + float(settings.RESOURCE_XTTS_IDLE_SECONDS) + 1.0]
        guardian = ResourceGuardian(FakeLLM(), voice, clock=lambda: now[0])
        guardian._last_tts_use = 1.0
        with patch.object(guardian, "sample", return_value=self.snap(ram=60)):
            released = guardian.idle_maintenance()
        self.assertTrue(released)
        self.assertFalse(voice.xtts_loaded)


class FakeHTTPResponse:
    status_code = 200

    def __init__(self, payload=None):
        self._payload = payload or {}

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class OllamaResourceAPITests(unittest.TestCase):
    def test_guardian_keep_alive_overrides_legacy_30m(self):
        provider = OllamaProvider("http://localhost:11434", "llama3.1")
        payload = provider._payload([{"role": "user", "content": "bonjour"}], stream=False)
        expected = settings.RESOURCE_LLM_KEEP_ALIVE_TEXT if settings.RESOURCE_GUARDIAN_ENABLED else settings.LLM_KEEP_ALIVE
        self.assertEqual(payload["keep_alive"], expected)

    def test_unload_uses_keep_alive_zero(self):
        provider = OllamaProvider("http://localhost:11434", "llama3.1")
        response = FakeHTTPResponse()
        with patch.object(provider.session, "post", return_value=response) as post:
            self.assertTrue(provider.unload())
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["keep_alive"], 0)
        self.assertEqual(body["model"], "llama3.1")

    def test_api_ps_exposes_matching_size_vram(self):
        provider = OllamaProvider("http://localhost:11434", "llama3.1")
        response = FakeHTTPResponse(
            {
                "models": [
                    {"name": "llama3.1:latest", "size": 5_300_000_000, "size_vram": 5_100_000_000},
                    {"name": "other:latest", "size_vram": 1},
                ]
            }
        )
        with patch.object(provider.session, "get", return_value=response):
            info = provider.running_model_info()
        self.assertIsNotNone(info)
        self.assertEqual(info["name"], "llama3.1:latest")
        self.assertEqual(info["size_vram"], 5_100_000_000)


if __name__ == "__main__":
    unittest.main()
