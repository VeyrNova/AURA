import unittest
from unittest.mock import patch

from config.settings import settings
from runtime.resource_guardian import ResourceGuardian, ResourceSnapshot, ResourcePressureError
from voice.voice_engine import VoiceEngine
from voice.gradium_tts import GradiumTTS
from voice.voice_profile import VoiceProfile


class _VoiceEngineFake:
    def release_stt_model(self): return True
    def release_xtts_model(self): return True
    def xtts_model_loaded(self): return False


class _LLMManagerFake:
    def __init__(self, running=None):
        self.running = running or {}
        self.unloaded = []
    def running_model_info(self, model=None):
        return self.running.get(model)
    def running_model_query_ok(self): return True
    def unload(self, model=None):
        self.unloaded.append(model); self.running.pop(model, None); return True
    def model_available(self, model): return True


class GPUOffloadRamSafetyTests(unittest.TestCase):
    def _guardian(self, *, running=None, snap=None):
        g = ResourceGuardian(_LLMManagerFake(running), _VoiceEngineFake())
        snapshot = snap or ResourceSnapshot(ram_used_pct=79.2, ram_total_gb=15.6, ram_available_gb=3.26, vram_used_mb=0, vram_total_mb=6141, gpu_name='NVIDIA GeForce RTX 4050 Laptop GPU')
        g.sample = lambda **kwargs: snapshot
        g._collect = lambda: None
        g._wait_model_unloaded = lambda model=None: True
        # Keep this unit test hermetic on Windows: the scenario models a
        # resident voice brain on the NVIDIA adapter, so physical telemetry
        # must be simulated too instead of leaking the developer PC's real
        # nvidia-smi state into the fixture.
        g._gpu_probe_source = "nvidia-smi"
        g._gpu_snapshot = lambda force=False: (1800.0, 6141.0, "NVIDIA GeForce RTX 4050 Laptop GPU")
        return g

    def test_cold_voice_brain_blocked_before_unsafe_ram_spike(self):
        g = self._guardian()
        profile = {'name':'voice-fast','provider':'local','model':settings.LLM_VOICE_MODEL,'co_resident':False,'keep_alive':'5m'}
        with self.assertRaises(ResourcePressureError):
            g.prepare_for_llm(profile)

    def test_resident_gpu_voice_brain_is_allowed(self):
        size = 2 * 1024**3
        running = {settings.LLM_VOICE_MODEL: {'name':settings.LLM_VOICE_MODEL,'size':size,'size_vram':int(size*0.85)}}
        g = self._guardian(running=running)
        profile = {'name':'voice-fast','provider':'local','model':settings.LLM_VOICE_MODEL,'co_resident':False,'keep_alive':'5m'}
        result = g.prepare_for_llm(profile)
        self.assertAlmostEqual(result.ram_used_pct, 79.2)

    def test_cpu_only_resident_voice_brain_rejected_under_pressure(self):
        size = 2 * 1024**3
        running = {settings.LLM_VOICE_MODEL: {'name':settings.LLM_VOICE_MODEL,'size':size,'size_vram':0}}
        g = self._guardian(running=running)
        profile = {'name':'voice-fast','provider':'local','model':settings.LLM_VOICE_MODEL,'co_resident':False,'keep_alive':'5m'}
        with self.assertRaises(ResourcePressureError):
            g.prepare_for_llm(profile)
        self.assertIn(settings.LLM_VOICE_MODEL, g.llm_manager.unloaded)

    def test_gpu_processor_summary_uses_size_vram(self):
        from ai.llm_manager import OllamaProvider
        provider = object.__new__(OllamaProvider)
        provider.model = settings.LLM_VOICE_MODEL
        provider.running_model_info = lambda model=None: {'name':model,'size':2000,'size_vram':1500}
        info = provider.model_processor_info(model=settings.LLM_VOICE_MODEL)
        self.assertEqual(info['processor'], '75% GPU')
        self.assertAlmostEqual(info['gpu_ratio'], 0.75)


class GradiumPersistenceTests(unittest.TestCase):
    def test_reload_same_gradium_backend_preserves_socket_instance(self):
        engine = object.__new__(VoiceEngine)
        old_profile = VoiceProfile(engine='gradium', fallback_engine='piper', gradium_voice_id='voice-a', gradium_voice_name='A')
        new_profile = VoiceProfile(engine='gradium', fallback_engine='piper', gradium_voice_id='voice-b', gradium_voice_name='B')
        backend = GradiumTTS(old_profile)
        sentinel = object()
        backend._ws = sentinel
        engine.profile_store = type('Store', (), {'save': lambda self, p: p.normalized(), 'load': lambda self: old_profile})()
        engine.profile = old_profile
        engine.tts = backend
        engine.fallback_tts = None
        engine._last_fallback_active = False
        engine._last_engine_used = ''
        engine._last_tts_error = ''
        engine._runtime_paused = False
        with patch.object(engine, '_build_tts', return_value=None):
            engine.reload_tts(new_profile)
        self.assertIs(engine.tts, backend)
        self.assertIs(engine.tts._ws, sentinel)
        self.assertEqual(engine.tts.profile.gradium_voice_id, 'voice-b')


if __name__ == '__main__':
    unittest.main()
