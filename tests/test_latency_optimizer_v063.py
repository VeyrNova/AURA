import json
import unittest
from pathlib import Path
from unittest.mock import patch

from ai.llm_manager import OllamaProvider
from config.settings import settings
from runtime.resource_guardian import ResourceGuardian, ResourceSnapshot


class FakeVoice:
    def release_xtts_model(self): return False
    def release_stt_model(self): return False
    def xtts_model_loaded(self): return False
    def release_heavy_models(self): return None


class FakeLLM:
    def __init__(self, running=None, query_ok=True):
        self.running = running
        self.query_ok = query_ok
        self.unload_calls = 0
    def running_model_info(self): return self.running
    def running_model_query_ok(self): return self.query_ok
    def unload(self):
        self.unload_calls += 1
        self.running = None
        return True


class StreamResponse:
    status_code = 200
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def raise_for_status(self): return None
    def iter_lines(self, decode_unicode=True):
        del decode_unicode
        rows = [
            {"message": {"content": "Salut"}, "done": False},
            {
                "message": {"content": ""}, "done": True,
                "total_duration": 3_000_000_000,
                "load_duration": 1_200_000_000,
                "prompt_eval_count": 120,
                "prompt_eval_duration": 300_000_000,
                "eval_count": 30,
                "eval_duration": 1_500_000_000,
            },
        ]
        for row in rows:
            yield json.dumps(row)


class LatencyOptimizerV063Tests(unittest.TestCase):
    def test_voice_profile_unloads_ollama_at_end_of_generation(self):
        guardian = ResourceGuardian(FakeLLM(), FakeVoice())
        profile = guardian.llm_request_profile(voice_output=True)
        self.assertEqual(str(profile["keep_alive"]), "0")
        self.assertEqual(profile["num_ctx"], settings.LLM_VOICE_NUM_CTX)
        self.assertEqual(profile["num_predict"], settings.LLM_VOICE_NUM_PREDICT)

    def test_text_profile_keeps_model_warm_briefly(self):
        guardian = ResourceGuardian(FakeLLM(), FakeVoice())
        profile = guardian.llm_request_profile(voice_output=False)
        expected = settings.RESOURCE_LLM_KEEP_ALIVE_TEXT if settings.RESOURCE_GUARDIAN_ENABLED else settings.LLM_KEEP_ALIVE
        self.assertEqual(profile["keep_alive"], expected)
        self.assertEqual(profile["num_ctx"], settings.LLM_NUM_CTX)

    def test_tts_handoff_skips_redundant_unload_when_ollama_already_gone(self):
        llm = FakeLLM(running=None)
        guardian = ResourceGuardian(llm, FakeVoice())
        snap = ResourceSnapshot(ram_used_pct=60, ram_total_gb=16, ram_available_gb=6,
                                vram_used_mb=1000, vram_total_mb=6144, vram_used_pct=16)
        with patch.object(guardian, "sample", return_value=snap), \
             patch.object(settings, "OPENGL_ORB_ENABLED", False):
            decision = guardian.prepare_for_tts()
        self.assertEqual(llm.unload_calls, 0)
        self.assertEqual(decision.backend, "xtts")
        self.assertTrue(decision.ollama_unloaded)

    def test_tts_handoff_does_not_trust_failed_ps_query(self):
        llm = FakeLLM(running=None, query_ok=False)
        guardian = ResourceGuardian(llm, FakeVoice())
        snap = ResourceSnapshot(ram_used_pct=60, ram_total_gb=16, ram_available_gb=6,
                                vram_used_mb=1000, vram_total_mb=6144, vram_used_pct=16)
        with patch.object(guardian, "_wait_ollama_unloaded", return_value=True), \
             patch.object(guardian, "sample", return_value=snap), \
             patch.object(settings, "OPENGL_ORB_ENABLED", False):
            decision = guardian.prepare_for_tts()
        self.assertEqual(llm.unload_calls, 1)
        self.assertEqual(decision.backend, "xtts")

    def test_ollama_stream_captures_native_timing_metrics(self):
        provider = OllamaProvider("http://localhost:11434", "test-model")
        with patch.object(provider.session, "post", return_value=StreamResponse()):
            chunks = list(provider.generate_stream(
                [{"role": "user", "content": "hello"}], keep_alive=0, num_ctx=3072, num_predict=160
            ))
        self.assertEqual(chunks, ["Salut"])
        metrics = provider.last_metrics
        self.assertAlmostEqual(metrics.load_seconds, 1.2, places=3)
        self.assertAlmostEqual(metrics.prompt_eval_seconds, 0.3, places=3)
        self.assertAlmostEqual(metrics.eval_seconds, 1.5, places=3)
        self.assertEqual(metrics.prompt_tokens, 120)
        self.assertEqual(metrics.output_tokens, 30)
        self.assertAlmostEqual(metrics.tokens_per_second, 20.0, places=2)
        self.assertEqual(metrics.keep_alive, "0")
        self.assertEqual(metrics.num_ctx, 3072)

    def test_prompt_forbids_fake_visual_observations(self):
        source = (Path(__file__).resolve().parents[1] / "consciousness" / "context_builder.py").read_text(encoding="utf-8")
        self.assertIn("N'invente aucune observation visuelle", source)
        self.assertIn("tu as l'air", source)
        self.assertIn("N'infere pas que l'utilisateur est actif", source)


if __name__ == "__main__":
    unittest.main()

class VoiceMetricPropagationV063Tests(unittest.TestCase):
    def test_voice_engine_returns_primary_tts_metrics(self):
        from voice.voice_engine import VoiceEngine
        engine = VoiceEngine()
        primary = engine.tts
        if primary is None:
            self.skipTest("No primary TTS configured")
        sentinel = object()
        with patch.object(engine, "_tts_available", side_effect=lambda obj: obj is primary), patch.object(primary, "speak", return_value=sentinel):
            result = engine.speak("bonjour", allow_fallback=False)
        self.assertIs(result, sentinel)


class NvidiaSmiDiscoveryV063Tests(unittest.TestCase):
    def test_guardian_can_use_which_for_nvidia_smi(self):
        with patch("runtime.resource_guardian.os.name", "nt"), patch("runtime.resource_guardian.shutil.which", return_value=r"C:\\Windows\\System32\\nvidia-smi.exe"):
            path = ResourceGuardian._find_nvidia_smi()
        self.assertTrue(path.lower().endswith("nvidia-smi.exe"))
