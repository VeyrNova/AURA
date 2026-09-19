from unittest import TestCase
from unittest.mock import patch
from pathlib import Path

from runtime.resource_guardian import ResourceGuardian, ResourceSnapshot


class _Voice:
    def xtts_model_loaded(self): return False
    def release_stt_model(self): return True
    def release_xtts_model(self): return True


class _LLM:
    def running_model_info(self, model=None): return None
    def running_model_query_ok(self): return True
    def unload(self, model=None): return True


class GPUCrashGuardTests(TestCase):
    def test_shared_6gb_display_gpu_blocks_cuda_xtts(self):
        guardian = ResourceGuardian(_LLM(), _Voice())
        snap = ResourceSnapshot(ram_used_pct=60, ram_total_gb=16, ram_available_gb=6,
                                vram_used_mb=1200, vram_total_mb=6141, vram_used_pct=19.5)
        with patch('runtime.resource_guardian.settings.XTTS_DEVICE', 'cuda'), \
             patch('runtime.resource_guardian.settings.XTTS_ALLOW_CUDA', True), \
             patch('runtime.resource_guardian.settings.OPENGL_ORB_ENABLED', True), \
             patch('runtime.resource_guardian.settings.XTTS_CUDA_DISPLAY_MIN_VRAM_MB', 8192):
            self.assertIn('seuil XTTS CUDA', guardian._display_gpu_guard_reason(snap, predicted_xtts_mb=1900))

    def test_unknown_vram_fails_closed_for_cuda_xtts(self):
        guardian = ResourceGuardian(_LLM(), _Voice())
        snap = ResourceSnapshot(ram_used_pct=50, ram_total_gb=16, ram_available_gb=8)
        with patch('runtime.resource_guardian.settings.XTTS_DEVICE', 'cuda'), \
             patch('runtime.resource_guardian.settings.XTTS_ALLOW_CUDA', True), \
             patch('runtime.resource_guardian.settings.OPENGL_ORB_ENABLED', True):
            self.assertIn('non mesurable', guardian._display_gpu_guard_reason(snap, predicted_xtts_mb=1900))

    def test_cpu_xtts_not_blocked_by_display_guard(self):
        guardian = ResourceGuardian(_LLM(), _Voice())
        snap = ResourceSnapshot(vram_used_mb=5000, vram_total_mb=6141, vram_used_pct=81.4)
        with patch('runtime.resource_guardian.settings.XTTS_DEVICE', 'cpu'), \
             patch('runtime.resource_guardian.settings.XTTS_ALLOW_CUDA', True), \
             patch('runtime.resource_guardian.settings.OPENGL_ORB_ENABLED', True):
            self.assertEqual(guardian._display_gpu_guard_reason(snap, predicted_xtts_mb=1900), '')

    def test_high_refresh_sync_never_raises_configured_budget(self):
        source = (Path(__file__).resolve().parents[1] / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertIn("math.ceil(refresh / preferred)", source)
        self.assertIn("144->48", source)
