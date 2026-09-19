import unittest
from unittest.mock import patch

from config.settings import settings
from runtime.hardware_runtime import hardware_runtime
from runtime.resource_guardian import ResourceGuardian, ResourceSnapshot
from regression_compat import assert_version_at_least


class Dummy:
    pass


class XTTSResidencyProbeTests(unittest.TestCase):
    def setUp(self):
        self.guardian = ResourceGuardian(Dummy(), Dummy())
        hardware_runtime.register_gl(vendor="Intel", renderer="Intel(R) Iris(R) Xe Graphics", version="4.6")
        hardware_runtime.register_compute(name="NVIDIA GeForce RTX 4050 Laptop GPU", used_mb=0, total_mb=6141)

    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.1.3.1")

    def test_probe_is_dry_run_and_ignores_shared_memory(self):
        snap = ResourceSnapshot(ram_used_pct=56, ram_total_gb=15.6, ram_available_gb=6.6,
                                vram_used_mb=0, vram_total_mb=6141, gpu_name="RTX 4050")
        with patch.object(self.guardian, "sample", return_value=snap), \
             patch.object(self.guardian, "_xtts_estimate_mb", return_value=1900.0):
            result = self.guardian.xtts_safe_residency_probe()
        self.assertTrue(result["dry_run"])
        self.assertTrue(result["eligible"])
        self.assertFalse(result["shared_memory_counted_for_cuda"])
        self.assertGreater(result["predicted_free_vram_mb"], result["vram_reserve_mb"])

    def test_probe_refuses_shared_display_compute(self):
        hardware_runtime.register_gl(vendor="NVIDIA", renderer="NVIDIA GeForce RTX 4050 Laptop GPU", version="4.6")
        snap = ResourceSnapshot(ram_used_pct=50, ram_total_gb=15.6, ram_available_gb=7.0,
                                vram_used_mb=0, vram_total_mb=6141, gpu_name="RTX 4050")
        with patch.object(self.guardian, "sample", return_value=snap), \
             patch.object(self.guardian, "_xtts_estimate_mb", return_value=1900.0):
            result = self.guardian.xtts_safe_residency_probe()
        self.assertFalse(result["eligible"])
        self.assertIn("display-compute-not-separated", result["reason"])

    def test_probe_refuses_low_ram(self):
        snap = ResourceSnapshot(ram_used_pct=85, ram_total_gb=15.6, ram_available_gb=2.0,
                                vram_used_mb=0, vram_total_mb=6141, gpu_name="RTX 4050")
        with patch.object(self.guardian, "sample", return_value=snap), \
             patch.object(self.guardian, "_xtts_estimate_mb", return_value=1900.0):
            result = self.guardian.xtts_safe_residency_probe()
        self.assertFalse(result["eligible"])
        self.assertIn("system-ram-headroom", result["reason"])

    def test_probe_refuses_low_dedicated_vram_margin(self):
        snap = ResourceSnapshot(ram_used_pct=55, ram_total_gb=15.6, ram_available_gb=6.5,
                                vram_used_mb=2800, vram_total_mb=6141, gpu_name="RTX 4050")
        with patch.object(self.guardian, "sample", return_value=snap), \
             patch.object(self.guardian, "_xtts_estimate_mb", return_value=1900.0):
            result = self.guardian.xtts_safe_residency_probe()
        self.assertFalse(result["eligible"])
        self.assertIn("dedicated-vram-headroom", result["reason"])


if __name__ == "__main__":
    unittest.main()
