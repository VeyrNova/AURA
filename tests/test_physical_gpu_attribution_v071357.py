import unittest
from unittest.mock import patch

from config.settings import settings
from runtime.resource_guardian import ResourceGuardian, ResourcePressureError


class _Voice:
    def xtts_model_loaded(self): return False


class _LLM:
    def __init__(self): self.unloaded=[]
    def unload(self, model=None): self.unloaded.append(model); return True


class PhysicalGpuAttributionTests(unittest.TestCase):
    def setUp(self):
        self.g=ResourceGuardian(_LLM(), _Voice())
        self.g._wait_model_unloaded=lambda model=None: True
        self.g._collect=lambda: None

    def test_version(self):
        self.assertEqual(settings.APP_VERSION, '0.7.2')

    def test_trusted_nvidia_memory_delta_confirms_physical_adapter(self):
        self.g._gpu_probe_source='nvidia-smi'
        self.g._gpu_snapshot=lambda force=False: (2240.0, 6141.0, 'NVIDIA GeForce RTX 4050 Laptop GPU')
        with patch('runtime.resource_guardian.os.name','nt'):
            ok, reason, data=self.g._verify_nvidia_physical_attribution(before_used_mb=0, claimed_vram_mb=2204)
        self.assertTrue(ok); self.assertEqual(reason,'confirmed'); self.assertGreater(data['nvidia_delta_mb'],2000)

    def test_ollama_gpu_claim_with_zero_nvidia_memory_is_rejected(self):
        self.g._gpu_probe_source='nvidia-smi'
        self.g._gpu_snapshot=lambda force=False: (0.0, 6141.0, 'NVIDIA GeForce RTX 4050 Laptop GPU')
        with patch('runtime.resource_guardian.os.name','nt'):
            ok, reason, _=self.g._verify_nvidia_physical_attribution(before_used_mb=0, claimed_vram_mb=2204)
        self.assertFalse(ok); self.assertEqual(reason,'nvidia-memory-not-observed')

    def test_generic_windows_counter_cannot_prove_rtx_attribution(self):
        self.g._gpu_probe_source='windows-counter+dual-marker'
        self.g._gpu_snapshot=lambda force=False: (2300.0, 6141.0, 'NVIDIA GeForce RTX 4050 Laptop GPU')
        with patch('runtime.resource_guardian.os.name','nt'):
            ok, reason, _=self.g._verify_nvidia_physical_attribution(before_used_mb=0, claimed_vram_mb=2204)
        self.assertFalse(ok); self.assertEqual(reason,'untrusted-telemetry')

    def test_postload_host_ram_guard_unloads_unsafe_voice_model(self):
        self.g._ram_snapshot=lambda: (98.0,15.6,0.31)
        with self.assertRaises(ResourcePressureError):
            self.g._enforce_postload_host_ram(settings.LLM_VOICE_MODEL)
        self.assertIn(settings.LLM_VOICE_MODEL,self.g.llm_manager.unloaded)

    def test_postload_host_ram_guard_accepts_safe_headroom(self):
        self.g._ram_snapshot=lambda: (72.0,15.6,4.3)
        self.g._enforce_postload_host_ram(settings.LLM_VOICE_MODEL)
        self.assertEqual(self.g.llm_manager.unloaded,[])


if __name__=='__main__': unittest.main()
