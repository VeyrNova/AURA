import unittest
from unittest.mock import patch

from runtime.resource_guardian import ResourceGuardian


class FakeLLM:
    def running_model_info(self, model=None): return None
    def running_models(self): return []


class FakeVoice:
    def xtts_model_loaded(self): return False


class NvidiaVRAMDetectionV0661Tests(unittest.TestCase):
    def test_prefers_nvidia_smi_when_it_returns_memory(self):
        g = ResourceGuardian(FakeLLM(), FakeVoice())
        with patch.object(g, "_run_nvidia_smi_detailed", return_value=(321.0, 6144.0, "RTX", r"C:\\nvidia-smi.exe", "ok")), \
             patch.object(g, "_run_nvml_ctypes") as nvml:
            used, total, name = g._probe_gpu_memory()
        self.assertEqual((used, total, name), (321.0, 6144.0, "RTX"))
        self.assertEqual(g._gpu_probe_source, "nvidia-smi")
        nvml.assert_not_called()

    def test_falls_back_to_nvml_when_nvidia_smi_fails(self):
        g = ResourceGuardian(FakeLLM(), FakeVoice())
        with patch.object(g, "_run_nvidia_smi_detailed", return_value=(0.0, 0.0, "", "", "timeout")), \
             patch.object(g, "_run_nvml_ctypes", return_value=(250.0, 6144.0, "RTX 4050", "nvml.dll")), \
             patch.object(g, "_run_windows_counter_fallback") as ps:
            used, total, name = g._probe_gpu_memory()
        self.assertEqual(total, 6144.0)
        self.assertEqual(name, "RTX 4050")
        self.assertEqual(g._gpu_probe_source, "nvml.dll")
        self.assertIn("timeout", g._gpu_probe_detail)
        ps.assert_not_called()

    def test_falls_back_to_windows_counter_after_nvml(self):
        g = ResourceGuardian(FakeLLM(), FakeVoice())
        with patch.object(g, "_run_nvidia_smi_detailed", return_value=(0.0, 0.0, "", "", "missing")), \
             patch.object(g, "_run_nvml_ctypes", return_value=(0.0, 0.0, "", "nvml missing")), \
             patch.object(g, "_run_windows_counter_fallback", return_value=(100.0, 6144.0, "RTX", "powershell.exe")):
            used, total, _ = g._probe_gpu_memory()
        self.assertEqual((used, total), (100.0, 6144.0))
        self.assertEqual(g._gpu_probe_source, "windows-counter+dual-marker")

    def test_fail_safe_when_all_gpu_methods_fail(self):
        g = ResourceGuardian(FakeLLM(), FakeVoice())
        with patch.object(g, "_run_nvidia_smi_detailed", return_value=(0.0, 0.0, "", "", "missing")), \
             patch.object(g, "_run_nvml_ctypes", return_value=(0.0, 0.0, "", "nvml missing")), \
             patch.object(g, "_run_windows_counter_fallback", return_value=(0.0, 0.0, "", "ps failed")):
            used, total, name = g._probe_gpu_memory()
        self.assertEqual((used, total, name), (0.0, 0.0, ""))
        self.assertEqual(g._gpu_probe_source, "unavailable")
        self.assertIn("ps failed", g._gpu_probe_detail)


if __name__ == "__main__":
    unittest.main()
