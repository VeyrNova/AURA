import unittest

from config.settings import settings
from runtime.hardware_runtime import HardwareRuntimeDiagnostics, classify_gpu_topology
from regression_compat import assert_version_at_least


class HardwareRuntimeDiagnosticsTests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.1.3.0")

    def test_intel_display_nvidia_compute_is_separated(self):
        separated, topology = classify_gpu_topology(
            "Intel(R) Iris(R) Xe Graphics", "NVIDIA GeForce RTX 4050 Laptop GPU"
        )
        self.assertTrue(separated)
        self.assertEqual(topology, "intel-display+nvidia-compute")

    def test_nvidia_renderer_and_compute_is_not_separated(self):
        separated, topology = classify_gpu_topology(
            "NVIDIA GeForce RTX 4050 Laptop GPU", "NVIDIA GeForce RTX 4050 Laptop GPU"
        )
        self.assertFalse(separated)
        self.assertIn(topology, {"nvidia-shared-display+compute", "same-adapter"})

    def test_shared_memory_never_counts_as_cuda_budget(self):
        diag = HardwareRuntimeDiagnostics()
        diag.register_gl(vendor="Intel", renderer="Intel Iris Xe", version="4.6")
        snap = diag.register_compute(name="NVIDIA RTX 4050", used_mb=2204, total_mb=6141)
        self.assertFalse(snap.shared_memory_counted_for_cuda)
        self.assertEqual(snap.compute_vram_total_mb, 6141)
        self.assertTrue(snap.display_compute_separated)

    def test_unknown_renderer_fails_closed_to_unknown(self):
        separated, topology = classify_gpu_topology("", "NVIDIA RTX 4050")
        self.assertIsNone(separated)
        self.assertEqual(topology, "unknown")


if __name__ == "__main__":
    unittest.main()
