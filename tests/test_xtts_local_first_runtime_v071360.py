import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import torch

from config.settings import settings
from runtime.hardware_runtime import hardware_runtime
from runtime.resource_guardian import ResourceGuardian, ResourceSnapshot
from voice.voice_engine import VoiceEngine
from voice.voice_profile import VoiceProfile
from voice.xtts_tts import XTTSTTS


class _FakeNativeModel:
    def __init__(self):
        self.speaker_manager = SimpleNamespace(
            speakers={
                "Ana Florence": {
                    "gpt_cond_latent": torch.zeros(1, 4, 8),
                    "speaker_embedding": torch.zeros(1, 512, 1),
                }
            }
        )

    def inference_stream(self, *args, **kwargs):
        yield torch.linspace(-0.1, 0.1, 1200)
        yield torch.linspace(-0.1, 0.1, 1200)


class _DummyLLM:
    def running_models(self):
        return []


class _DummyVoice:
    profile = SimpleNamespace(engine="xtts")

    def xtts_model_loaded(self):
        return False


class XTTSLocalFirstRuntimeV071360Tests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(settings.APP_VERSION, "0.7.2")

    def test_cloud_selection_promotes_xtts_in_runtime_and_preserves_cloud_fallback(self):
        engine = VoiceEngine.__new__(VoiceEngine)
        engine.profile = VoiceProfile(engine="gradium", fallback_engine="piper", cloud_fallback_engine="none")
        with patch.object(settings, "XTTS_LOCAL_FIRST_ENABLED", True), \
             patch.object(settings, "XTTS_ALLOW_CUDA", True), \
             patch.object(settings, "XTTS_DEVICE", "cuda"):
            VoiceEngine._apply_local_first_runtime_profile(engine)
        self.assertEqual(engine.profile.engine, "xtts")
        self.assertEqual(engine.profile.cloud_fallback_engine, "gradium")
        self.assertEqual(engine.profile.fallback_engine, "piper")

    def test_silent_native_warmup_consumes_multiple_chunks_without_audio_device(self):
        backend = XTTSTTS(VoiceProfile(xtts_mode="preset", xtts_preset="Ana Florence", xtts_language="fr"))
        backend._device = "cuda"
        model = _FakeNativeModel()
        api = SimpleNamespace(synthesizer=SimpleNamespace(tts_model=model))
        with patch.object(backend, "_load_model", return_value=api):
            result = backend.native_silent_warmup("Prêt.")
        self.assertTrue(result["ok"])
        self.assertEqual(result["chunk_count"], 2)
        self.assertGreater(result["first_chunk_seconds"], 0.0)

    def test_display_guard_allows_6gb_nvidia_when_intel_display_is_separate(self):
        guardian = ResourceGuardian(_DummyLLM(), _DummyVoice())
        hardware_runtime.register_gl(vendor="Intel", renderer="Intel(R) Iris(R) Xe Graphics", version="4.6")
        hardware_runtime.register_compute(name="NVIDIA GeForce RTX 4050 Laptop GPU", used_mb=0, total_mb=6141)
        snap = ResourceSnapshot(vram_used_mb=0, vram_total_mb=6141, gpu_name="NVIDIA GeForce RTX 4050 Laptop GPU")
        with patch.object(settings, "XTTS_ALLOW_CUDA", True), \
             patch.object(settings, "XTTS_DEVICE", "cuda"), \
             patch.object(settings, "OPENGL_ORB_ENABLED", True), \
             patch.object(settings, "XTTS_CUDA_DISPLAY_MIN_VRAM_MB", 8192), \
             patch.object(settings, "XTTS_SAFE_PROBE_VRAM_RESERVE_MB", 1200):
            reason = guardian._display_gpu_guard_reason(snap, predicted_xtts_mb=1838)
        self.assertEqual(reason, "")

    def test_voice_brain_prewarm_is_disabled_when_xtts_local_first_owns_gpu_priority(self):
        guardian = ResourceGuardian(_DummyLLM(), _DummyVoice())
        with patch.object(settings, "XTTS_LOCAL_FIRST_ENABLED", True), \
             patch.object(settings, "XTTS_ALLOW_CUDA", True), \
             patch.object(settings, "XTTS_DEVICE", "cuda"):
            self.assertFalse(guardian.conditional_voice_llm_prewarm())
        self.assertEqual(guardian._voice_llm_prewarm_last_result, "xtts-local-first-priority")


if __name__ == "__main__":
    unittest.main()
