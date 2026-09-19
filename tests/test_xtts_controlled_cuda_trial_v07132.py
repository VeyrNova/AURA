import unittest
from unittest.mock import Mock, patch
from pathlib import Path

from config.settings import settings
from runtime.hardware_runtime import hardware_runtime
from runtime.resource_guardian import ResourceGuardian, ResourceSnapshot
from regression_compat import assert_version_at_least


class DummyLLM:
    def running_models(self):
        return []


class DummyVoice:
    def __init__(self):
        self.released = 0

    def warmup_xtts_only(self):
        return True

    def probe_xtts_inference(self, text):
        return {
            "device": "cuda",
            "synthesis_seconds": 0.42,
            "model_load_seconds": 0.0,
            "cuda_allocated_mb": 1780.0,
            "cuda_reserved_mb": 1900.0,
            "gpu_name": "NVIDIA GeForce RTX 4050 Laptop GPU",
        }

    def release_xtts_model(self):
        self.released += 1
        return True


class XTTSControlledCudaTrialV07132Tests(unittest.TestCase):
    def setUp(self):
        hardware_runtime.register_gl(vendor="Intel", renderer="Intel(R) Iris(R) Xe Graphics", version="4.6")
        hardware_runtime.register_compute(name="NVIDIA GeForce RTX 4050 Laptop GPU", used_mb=0, total_mb=6141)
        self.voice = DummyVoice()
        self.guardian = ResourceGuardian(DummyLLM(), self.voice)

    def _snap(self, *, ram=58.0, avail=6.5, used=0.0):
        return ResourceSnapshot(
            ram_used_pct=ram, ram_total_gb=15.6, ram_available_gb=avail,
            vram_used_mb=used, vram_total_mb=6141, gpu_name="RTX 4050",
        )

    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.1.3.2")

    def test_controlled_trial_passes_and_releases_by_default(self):
        probe = {"eligible": True, "reason": "pass-dry-run", "topology": "intel-display+nvidia-compute"}
        samples = [
            self._snap(used=0),       # before
            self._snap(ram=65, avail=5.4, used=1911),  # after load
            self._snap(ram=66, avail=5.2, used=1950),  # after inference
            self._snap(ram=59, avail=6.3, used=0),     # cleanup
        ]
        with patch.object(settings, "XTTS_CONTROLLED_TRIAL_ENABLED", True), \
             patch.object(settings, "XTTS_ALLOW_CUDA", True), \
             patch.object(settings, "XTTS_DEVICE", "cuda"), \
             patch.object(settings, "XTTS_CONTROLLED_TRIAL_KEEP_LOADED", False), \
             patch.object(self.guardian, "sample", side_effect=samples):
            result = self.guardian.controlled_xtts_cuda_trial(probe)
        self.assertTrue(result["attempted"])
        self.assertTrue(result["passed"])
        self.assertEqual(result["reason"], "pass-controlled-trial")
        self.assertEqual(result["device"], "cuda")
        self.assertEqual(self.voice.released, 1)

    def test_trial_rolls_back_when_postload_vram_margin_is_low(self):
        probe = {"eligible": True, "reason": "pass-dry-run", "topology": "intel-display+nvidia-compute"}
        samples = [
            self._snap(used=0),
            self._snap(ram=65, avail=5.4, used=5200),
            self._snap(ram=59, avail=6.3, used=0),
        ]
        with patch.object(settings, "XTTS_CONTROLLED_TRIAL_ENABLED", True), \
             patch.object(settings, "XTTS_ALLOW_CUDA", True), \
             patch.object(settings, "XTTS_DEVICE", "cuda"), \
             patch.object(self.guardian, "sample", side_effect=samples):
            result = self.guardian.controlled_xtts_cuda_trial(probe)
        self.assertFalse(result["passed"])
        self.assertEqual(result["reason"], "postload-vram-headroom")
        self.assertEqual(self.voice.released, 1)

    def test_trial_does_not_start_if_dry_probe_is_unsafe(self):
        with patch.object(settings, "XTTS_CONTROLLED_TRIAL_ENABLED", True), \
             patch.object(settings, "XTTS_ALLOW_CUDA", True), \
             patch.object(settings, "XTTS_DEVICE", "cuda"):
            result = self.guardian.controlled_xtts_cuda_trial({"eligible": False, "reason": "system-ram-headroom"})
        self.assertFalse(result["attempted"])
        self.assertIn("dry-probe", result["reason"])
        self.assertEqual(self.voice.released, 0)

    def test_trial_does_not_start_while_ollama_is_resident(self):
        llm = Mock()
        llm.running_models.return_value = [{"name": "llama3.2:3b", "size_vram": 1024}]
        guardian = ResourceGuardian(llm, self.voice)
        with patch.object(settings, "XTTS_CONTROLLED_TRIAL_ENABLED", True), \
             patch.object(settings, "XTTS_ALLOW_CUDA", True), \
             patch.object(settings, "XTTS_DEVICE", "cuda"):
            result = guardian.controlled_xtts_cuda_trial({"eligible": True, "reason": "pass-dry-run"})
        self.assertFalse(result["attempted"])
        self.assertEqual(result["reason"], "ollama-resident")

    def test_ui_runs_dry_probe_before_controlled_trial(self):
        source = Path("ui/main_window.py").read_text(encoding="utf-8")
        self.assertLess(source.index("xtts_safe_residency_probe()"), source.index("controlled_xtts_cuda_trial(probe)"))


if __name__ == "__main__":
    unittest.main()
