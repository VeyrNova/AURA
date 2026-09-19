from regression_compat import assert_version_at_least
import unittest
from unittest.mock import patch

from config.settings import settings
from consciousness.context_builder import ConsciousnessContextBuilder
from runtime.resource_guardian import ResourceGuardian, ResourceSnapshot


class FakeVoice:
    def __init__(self):
        self.xtts_loaded = True
        self.xtts_releases = 0

    def xtts_model_loaded(self):
        return self.xtts_loaded

    def release_xtts_model(self):
        self.xtts_releases += 1
        was_loaded = self.xtts_loaded
        self.xtts_loaded = False
        return was_loaded

    def release_stt_model(self):
        return True


class FakeLLM:
    def __init__(self, *, resident=True, unload_ok=True, query_ok=True):
        self.resident = resident
        self.unload_ok = unload_ok
        self.query_ok = query_ok
        self.unloaded_models = []

    def running_model_info(self, model=None):
        if self.resident and (model is None or str(model).casefold() == settings.LLM_VOICE_MODEL.casefold()):
            return {
                "name": settings.LLM_VOICE_MODEL,
                "size": 2_000_000_000,
                "size_vram": 2_000_000_000,
            }
        return None

    def running_model_query_ok(self):
        return self.query_ok

    def unload(self, model=None):
        self.unloaded_models.append(model)
        if self.unload_ok and str(model).casefold() == settings.LLM_VOICE_MODEL.casefold():
            self.resident = False
        return self.unload_ok


class VoiceResidencyPriorityTests(unittest.TestCase):
    @staticmethod
    def snap(ram):
        return ResourceSnapshot(
            ram_used_pct=float(ram),
            ram_total_gb=15.6,
            ram_available_gb=max(0.2, 15.6 * (100.0 - float(ram)) / 100.0),
            vram_used_mb=2375,
            vram_total_mb=6141,
            vram_used_pct=38.7,
            gpu_name="RTX Test",
        )

    def test_version_and_priority_defaults(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.6")
        self.assertTrue(settings.VOICE_RESIDENCY_PRIORITY)
        self.assertGreaterEqual(settings.VOICE_RESIDENCY_RELEASE_LLM_RAM_PCT, 80)

    def test_critical_pressure_evicts_voice_llm_and_keeps_xtts(self):
        llm = FakeLLM(resident=True)
        voice = FakeVoice()
        guardian = ResourceGuardian(llm, voice, clock=lambda: 100.0)
        guardian._last_tts_use = 100.0
        guardian._last_llm_profile = {
            "name": "voice-fast",
            "model": settings.LLM_VOICE_MODEL,
            "co_resident": True,
            "keep_alive": settings.DUAL_BRAIN_VOICE_KEEP_ALIVE,
        }
        with patch.object(guardian, "dual_brain_co_resident_ready", return_value=True), patch.object(
            guardian, "sample", side_effect=[self.snap(94.2), self.snap(61.8)]
        ):
            acted = guardian.idle_maintenance()

        self.assertTrue(acted)
        self.assertIn(settings.LLM_VOICE_MODEL, llm.unloaded_models)
        self.assertTrue(voice.xtts_loaded)
        self.assertEqual(voice.xtts_releases, 0)
        self.assertFalse(guardian._last_llm_profile["co_resident"])
        self.assertIn("cerveau vocal libéré", guardian.last_decision)

    def test_persistent_pressure_falls_back_to_releasing_xtts(self):
        llm = FakeLLM(resident=True)
        voice = FakeVoice()
        guardian = ResourceGuardian(llm, voice, clock=lambda: 100.0)
        guardian._last_tts_use = 100.0
        with patch.object(guardian, "dual_brain_co_resident_ready", return_value=True), patch.object(
            guardian, "sample", side_effect=[self.snap(95.0), self.snap(94.7)]
        ):
            acted = guardian.idle_maintenance()

        self.assertTrue(acted)
        self.assertFalse(voice.xtts_loaded)
        self.assertEqual(voice.xtts_releases, 1)
        self.assertIn("pression mémoire persistante", guardian.last_decision)

    def test_inactivity_still_releases_xtts_when_ram_is_normal(self):
        llm = FakeLLM(resident=False)
        voice = FakeVoice()
        now = [500.0]
        guardian = ResourceGuardian(llm, voice, clock=lambda: now[0])
        guardian._last_tts_use = 1.0
        with patch.object(guardian, "dual_brain_co_resident_ready", return_value=False), patch.object(
            guardian, "sample", return_value=self.snap(60.0)
        ):
            acted = guardian.idle_maintenance()

        self.assertTrue(acted)
        self.assertFalse(voice.xtts_loaded)
        self.assertEqual(voice.xtts_releases, 1)

    def test_failed_voice_llm_unload_preserves_fail_safe(self):
        llm = FakeLLM(resident=True, unload_ok=False)
        voice = FakeVoice()
        guardian = ResourceGuardian(llm, voice, clock=lambda: 100.0)
        guardian._last_tts_use = 100.0
        with patch.object(guardian, "dual_brain_co_resident_ready", return_value=True), patch.object(
            guardian, "sample", return_value=self.snap(95.0)
        ), patch.object(guardian, "_wait_model_unloaded", return_value=False):
            acted = guardian.idle_maintenance()

        self.assertTrue(acted)
        self.assertFalse(voice.xtts_loaded)
        self.assertEqual(voice.xtts_releases, 1)

    def test_fast_voice_prompt_contains_french_language_polish(self):
        prompt = ConsciousnessContextBuilder(user_name="").build_system_prompt(compact=True)
        self.assertIn("accords de genre et de nombre corrects", prompt)
        self.assertIn("pronoms coherents", prompt)
        self.assertIn("syntaxe simple sujet-verbe-complement", prompt)
        self.assertIn("verifie mentalement la derniere phrase", prompt)


if __name__ == "__main__":
    unittest.main()
