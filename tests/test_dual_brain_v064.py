from regression_compat import assert_version_at_least
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai.llm_manager import OllamaProvider
from config.settings import settings
from consciousness.context_builder import ConsciousnessContextBuilder
from runtime.resource_guardian import ResourceGuardian, ResourceSnapshot
from voice.xtts_tts import XTTSSynthesisMetrics


class FakeVoice:
    def __init__(self, loaded=False):
        self.loaded = loaded
        self.xtts_releases = 0
        self.stt_releases = 0
    def release_xtts_model(self):
        self.xtts_releases += 1
        was = self.loaded
        self.loaded = False
        return was
    def release_stt_model(self):
        self.stt_releases += 1
        return True
    def xtts_model_loaded(self): return self.loaded
    def release_heavy_models(self): self.release_xtts_model(); self.release_stt_model()


class FakeLLM:
    def __init__(self, *, available=True, running=None, query_ok=True):
        self.available = available
        self.running = running or {}
        self.query_ok = query_ok
        self.unloaded = []
    def model_available(self, model): return self.available if model == settings.LLM_VOICE_MODEL else True
    def running_model_info(self, model=None): return self.running.get(model or settings.LLM_TEXT_MODEL)
    def running_model_query_ok(self): return self.query_ok
    def unload(self, model=None):
        model = model or settings.LLM_TEXT_MODEL
        self.unloaded.append(model)
        self.running.pop(model, None)
        return True


def snap(ram=55, used=1500, total=6144, ollama=0, name="RTX 4050"):
    return ResourceSnapshot(
        ram_used_pct=ram, ram_total_gb=16, ram_available_gb=7,
        vram_used_mb=used, vram_total_mb=total,
        vram_used_pct=(100*used/total if total else 0), gpu_name=name,
        ollama_vram_mb=ollama,
    )


class FakeResponse:
    status_code = 200
    def __init__(self, payload): self.payload = payload
    def raise_for_status(self): return None
    def json(self): return self.payload


class DualBrainV064Tests(unittest.TestCase):
    def test_version_keeps_dual_brain_generation(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.6.4")

    def test_ollama_payload_accepts_model_override(self):
        provider = OllamaProvider("http://localhost:11434", "llama3.1")
        payload = provider._payload([], stream=False, model="llama3.2:3b", num_ctx=2048, num_predict=96)
        self.assertEqual(payload["model"], "llama3.2:3b")
        self.assertEqual(payload["options"]["num_ctx"], 2048)

    def test_model_available_uses_tags_and_respects_tag(self):
        provider = OllamaProvider("http://localhost:11434", "llama3.1")
        response = FakeResponse({"models": [{"name": "llama3.2:3b"}, {"name": "llama3.1:latest"}]})
        with patch.object(provider.session, "get", return_value=response):
            self.assertTrue(provider.model_available("llama3.2:3b"))
            self.assertFalse(provider.model_available("llama3.2:1b"))
            self.assertTrue(provider.model_available("llama3.1"))

    def test_voice_profile_uses_fast_model_when_installed(self):
        guardian = ResourceGuardian(FakeLLM(available=True), FakeVoice())
        with patch.object(guardian, "dual_brain_co_resident_ready", return_value=False):
            profile = guardian.llm_request_profile(voice_output=True)
        self.assertEqual(profile["model"], settings.LLM_VOICE_MODEL)
        self.assertEqual(profile["name"], "voice-fast")
        self.assertEqual(str(profile["keep_alive"]), settings.VOICE_BRAIN_INDEPENDENT_KEEP_ALIVE)
        self.assertTrue(profile.get("independent_resident"))
        self.assertTrue(profile["compact"])

    def test_voice_profile_falls_back_to_text_model_if_fast_missing(self):
        guardian = ResourceGuardian(FakeLLM(available=False), FakeVoice())
        profile = guardian.llm_request_profile(voice_output=True)
        self.assertEqual(profile["model"], settings.LLM_TEXT_MODEL)
        self.assertEqual(profile["name"], "voice-safe")
        self.assertFalse(profile["co_resident"])

    def test_valid_marker_enables_warm_voice_keep_alive(self):
        with tempfile.TemporaryDirectory() as td:
            marker = Path(td) / "dual.json"
            marker.write_text(json.dumps({"passed": True, "voice_model": settings.LLM_VOICE_MODEL,
                                          "gpu_name": "RTX 4050", "vram_total_mb": 6144,
                                          "xtts_vram_mb": 2200}), encoding="utf-8")
            guardian = ResourceGuardian(FakeLLM(available=True), FakeVoice())
            with patch.object(settings, "DUAL_BRAIN_MARKER", marker), \
                 patch.object(settings, "OPENGL_ORB_ENABLED", False), \
                 patch.object(guardian, "sample", return_value=snap()):
                profile = guardian.llm_request_profile(voice_output=True)
            self.assertTrue(profile["co_resident"])
            self.assertEqual(profile["keep_alive"], settings.DUAL_BRAIN_VOICE_KEEP_ALIVE)

    def test_prepare_voice_coresident_does_not_release_xtts(self):
        voice = FakeVoice(loaded=True)
        llm = FakeLLM(available=True)
        guardian = ResourceGuardian(llm, voice)
        profile = {"name":"voice-fast", "model":settings.LLM_VOICE_MODEL, "co_resident":True,
                   "keep_alive":"5m", "compact":True}
        with patch.object(guardian, "sample", return_value=snap(ram=60, used=2600)):
            guardian.prepare_for_llm(profile=profile)
        self.assertEqual(voice.xtts_releases, 0)

    def test_prepare_text_releases_xtts_and_unloads_voice_brain(self):
        voice = FakeVoice(loaded=True)
        llm = FakeLLM(running={settings.LLM_VOICE_MODEL:{"name":settings.LLM_VOICE_MODEL,"size_vram":2_000_000_000}})
        guardian = ResourceGuardian(llm, voice)
        profile = {"name":"text", "model":settings.LLM_TEXT_MODEL, "co_resident":False,
                   "keep_alive":"2m", "compact":False}
        with patch.object(guardian, "sample", return_value=snap(ram=60)), patch.object(guardian, "_wait_model_unloaded", return_value=True):
            guardian.prepare_for_llm(profile=profile)
        self.assertEqual(voice.xtts_releases, 1)
        self.assertIn(settings.LLM_VOICE_MODEL, llm.unloaded)

    def test_prepare_tts_keeps_fast_brain_when_marker_safe(self):
        voice = FakeVoice(loaded=True)
        llm = FakeLLM(running={settings.LLM_VOICE_MODEL:{"name":settings.LLM_VOICE_MODEL,"size_vram":1_900*1024*1024}})
        guardian = ResourceGuardian(llm, voice)
        guardian._last_llm_profile = {"name":"voice-fast", "model":settings.LLM_VOICE_MODEL, "co_resident":True}
        with patch.object(guardian, "dual_brain_co_resident_ready", return_value=True), \
             patch.object(guardian, "sample", return_value=snap(ram=60, used=3900, ollama=1900)), \
             patch.object(settings, "XTTS_CUDA_DISPLAY_MIN_VRAM_MB", 4096):
            decision = guardian.prepare_for_tts()
        self.assertEqual(decision.backend, "xtts")
        self.assertFalse(decision.ollama_unloaded)
        self.assertNotIn(settings.LLM_VOICE_MODEL, llm.unloaded)

    def test_compact_prompt_is_shorter_and_keeps_security(self):
        builder = ConsciousnessContextBuilder()
        full = builder.build_system_prompt(memory_context="MEMOIRE\n- test")
        compact = builder.build_system_prompt(memory_context="MEMORY CONTEXT\n- test", compact=True)
        self.assertLess(len(compact), len(full) * 0.65)
        self.assertIn("DONNEE NON FIABLE", compact)
        self.assertIn("N'invente jamais une observation", compact)
        self.assertIn("SecurityPolicyEngine", compact)

    def test_xtts_metrics_expose_true_first_audio(self):
        m = XTTSSynthesisMetrics("cuda", 2.0, 3.0, 9.0, 50, model_load_seconds=4.0, time_to_audio_seconds=6.0)
        self.assertEqual(m.time_to_audio_seconds, 6.0)
        self.assertEqual(m.model_load_seconds, 4.0)

    def test_probe_and_install_launchers_exist(self):
        root = Path(__file__).resolve().parents[1]
        self.assertTrue((root / "INSTALL_DUAL_BRAIN.bat").is_file())
        self.assertTrue((root / "DUAL_GPU_PROBE.bat").is_file())
        self.assertTrue((root / "DUAL_BRAIN_STATUS.bat").is_file())


if __name__ == "__main__":
    unittest.main()
