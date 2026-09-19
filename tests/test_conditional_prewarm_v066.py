import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config.settings import settings
from runtime.resource_guardian import ResourceGuardian, ResourceSnapshot


class FakeLLM:
    def __init__(self, running=None):
        self._running = list(running or [])
    def running_models(self): return list(self._running)
    def running_model_info(self, model=None): return None
    def model_available(self, model): return True
    def unload(self, model=None): return True


class FakeVoice:
    def __init__(self):
        self.loaded = False
        self.warmups = 0
        self.releases = 0
    def xtts_model_loaded(self): return self.loaded
    def warmup_xtts_only(self):
        self.warmups += 1
        self.loaded = True
        return True
    def release_xtts_model(self):
        self.releases += 1
        was = self.loaded
        self.loaded = False
        return was
    def release_stt_model(self): return True
    def release_heavy_models(self): self.release_xtts_model()


def snap(ram=45.0, avail=8.0, used=100.0, total=6144.0):
    return ResourceSnapshot(
        ram_used_pct=ram, ram_total_gb=16.0, ram_available_gb=avail,
        vram_used_mb=used, vram_total_mb=total, vram_used_pct=(100.0*used/total if total else 0.0),
        gpu_name="RTX Test",
    )


class ConditionalPrewarmV066Tests(unittest.TestCase):
    def marker(self, folder: str) -> Path:
        path = Path(folder) / "dual.json"
        path.write_text(json.dumps({
            "passed": True,
            "voice_model": settings.LLM_VOICE_MODEL,
            "gpu_name": "RTX Test",
            "vram_total_mb": 6144,
            "xtts_vram_mb": 1900,
        }), encoding="utf-8")
        return path

    def test_prewarm_loads_xtts_only_with_safe_headroom(self):
        with tempfile.TemporaryDirectory() as td:
            voice = FakeVoice()
            guardian = ResourceGuardian(FakeLLM(), voice)
            marker = self.marker(td)
            samples = [snap(ram=45, avail=8), snap(ram=72, avail=4.4, used=2050)]
            with patch.object(settings, "DUAL_BRAIN_MARKER", marker), \
                 patch.object(settings, "XTTS_DEVICE", "cuda"), patch.object(settings, "XTTS_ALLOW_CUDA", True), \
                 patch.object(settings, "XTTS_CUDA_DISPLAY_MIN_VRAM_MB", 0), \
                 patch.object(guardian, "dual_brain_co_resident_ready", return_value=True), \
                 patch.object(guardian, "sample", side_effect=samples):
                self.assertTrue(guardian.conditional_xtts_prewarm())
            self.assertEqual(voice.warmups, 1)
            self.assertTrue(voice.loaded)

    def test_prewarm_allows_moderate_ram_when_available_headroom_is_safe(self):
        with tempfile.TemporaryDirectory() as td:
            voice = FakeVoice()
            guardian = ResourceGuardian(FakeLLM(), voice)
            marker = self.marker(td)
            with patch.object(settings, "DUAL_BRAIN_MARKER", marker), \
                 patch.object(settings, "XTTS_DEVICE", "cuda"), patch.object(settings, "XTTS_ALLOW_CUDA", True), \
                 patch.object(settings, "XTTS_CUDA_DISPLAY_MIN_VRAM_MB", 0), \
                 patch.object(guardian, "dual_brain_co_resident_ready", return_value=True), \
                 patch.object(guardian, "sample", return_value=snap(ram=70, avail=4)):
                self.assertTrue(guardian.conditional_xtts_prewarm())
            self.assertEqual(voice.warmups, 1)

    def test_prewarm_refuses_when_ollama_is_resident(self):
        with tempfile.TemporaryDirectory() as td:
            voice = FakeVoice()
            guardian = ResourceGuardian(FakeLLM(running=[{"name":"llama3.2:3b"}]), voice)
            marker = self.marker(td)
            with patch.object(settings, "DUAL_BRAIN_MARKER", marker), \
                 patch.object(settings, "XTTS_DEVICE", "cuda"), patch.object(settings, "XTTS_ALLOW_CUDA", True), \
                 patch.object(settings, "XTTS_CUDA_DISPLAY_MIN_VRAM_MB", 0), \
                 patch.object(guardian, "dual_brain_co_resident_ready", return_value=True), \
                 patch.object(guardian, "sample", return_value=snap()):
                self.assertFalse(guardian.conditional_xtts_prewarm())
            self.assertEqual(voice.warmups, 0)

    def test_prewarm_rolls_back_if_ram_becomes_critical(self):
        with tempfile.TemporaryDirectory() as td:
            voice = FakeVoice()
            guardian = ResourceGuardian(FakeLLM(), voice)
            marker = self.marker(td)
            samples = [snap(ram=45, avail=8), snap(ram=90, avail=1.4, used=2100)]
            with patch.object(settings, "DUAL_BRAIN_MARKER", marker), \
                 patch.object(settings, "XTTS_DEVICE", "cuda"), patch.object(settings, "XTTS_ALLOW_CUDA", True), \
                 patch.object(settings, "XTTS_CUDA_DISPLAY_MIN_VRAM_MB", 0), \
                 patch.object(guardian, "dual_brain_co_resident_ready", return_value=True), \
                 patch.object(guardian, "sample", side_effect=samples):
                self.assertFalse(guardian.conditional_xtts_prewarm())
            self.assertFalse(voice.loaded)
            self.assertEqual(voice.releases, 1)

    def test_prewarm_refuses_without_vram_measurement(self):
        with tempfile.TemporaryDirectory() as td:
            voice = FakeVoice()
            guardian = ResourceGuardian(FakeLLM(), voice)
            marker = self.marker(td)
            no_gpu = snap(ram=45, avail=8, used=0, total=0)
            with patch.object(settings, "DUAL_BRAIN_MARKER", marker), \
                 patch.object(settings, "XTTS_DEVICE", "cuda"), patch.object(settings, "XTTS_ALLOW_CUDA", True), \
                 patch.object(settings, "XTTS_CUDA_DISPLAY_MIN_VRAM_MB", 0), \
                 patch.object(guardian, "dual_brain_co_resident_ready", return_value=True), \
                 patch.object(guardian, "sample", return_value=no_gpu):
                self.assertFalse(guardian.conditional_xtts_prewarm())
            self.assertEqual(voice.warmups, 0)



if __name__ == "__main__":
    unittest.main()
