from regression_compat import assert_version_at_least
import unittest
from unittest.mock import patch

from ai.response_guard import (
    complete_sentence_prefix,
    finalize_voice_reply,
    looks_incomplete,
    merge_continuation,
    needs_voice_completion,
    trim_incomplete_tail,
)
from config.settings import settings
from runtime.resource_guardian import ResourceGuardian, ResourceSnapshot
from voice.xtts_tts import XTTSTTS


class ResponseGuardTests(unittest.TestCase):
    def test_version_and_voice_budget(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.5")
        self.assertGreaterEqual(settings.LLM_VOICE_NUM_PREDICT, 96)
        self.assertTrue(settings.LLM_VOICE_COMPLETION_GUARD)
        self.assertGreaterEqual(settings.LLM_VOICE_COMPLETION_NUM_PREDICT, 32)

    def test_neutron_log_fragment_is_detected_at_budget(self):
        text = "Les neutrons ont une masse équivalente à celle des protons ("
        self.assertTrue(looks_incomplete(text))
        self.assertTrue(
            needs_voice_completion(
                text,
                output_tokens=128,
                num_predict=128,
                margin=4,
            )
        )

    def test_complete_sentence_is_not_extended_even_at_budget(self):
        text = "Les neutrons sont présents dans le noyau atomique."
        self.assertFalse(
            needs_voice_completion(
                text,
                output_tokens=128,
                num_predict=128,
                margin=4,
            )
        )

    def test_low_token_incomplete_text_does_not_trigger_second_generation(self):
        self.assertFalse(
            needs_voice_completion(
                "Voici une liste :",
                output_tokens=20,
                num_predict=128,
                margin=4,
            )
        )

    def test_merge_continuation_deduplicates_overlap(self):
        original = "AURA peut terminer la phrase avec une transition"
        continuation = "une transition naturelle et propre."
        merged = merge_continuation(original, continuation)
        self.assertEqual(merged.count("une transition"), 1)
        self.assertTrue(merged.endswith("propre."))

    def test_trim_incomplete_tail_keeps_last_complete_sentence(self):
        text = "Première phrase complète. Deuxième phrase complète. Fragment final ("
        self.assertEqual(trim_incomplete_tail(text), "Première phrase complète. Deuxième phrase complète.")

    def test_sentence_safe_prefix_holds_dangling_tail(self):
        prefix, tail = complete_sentence_prefix("Première phrase. Deuxième phrase encore")
        self.assertEqual(prefix.strip(), "Première phrase.")
        self.assertEqual(tail, "Deuxième phrase encore")

    def test_fast_prosody_first_chunk_is_first_complete_sentence(self):
        text = (
            "À Vidauban, Région PACA, France, il fait actuellement 36 virgule 2 degrés Celsius. "
            "Conditions actuelles : ciel dégagé. "
            "Le ressenti est de 35 virgule 2 degrés Celsius."
        )
        plan = XTTSTTS._natural_chunk_plan(
            text,
            first_limit=120,
            next_limit=170,
            min_chars=48,
            max_chunks=8,
        )
        self.assertGreaterEqual(len(plan), 2)
        self.assertTrue(plan[0].text.endswith("Celsius."))
        self.assertNotIn("Conditions actuelles", plan[0].text)
        self.assertEqual(plan[0].boundary, "sentence")


class _FakeVoice:
    def __init__(self):
        self.xtts_loaded = True
        self.xtts_releases = 0
        self.stt_releases = 0

    def release_stt_model(self):
        self.stt_releases += 1
        return True

    def release_xtts_model(self):
        self.xtts_releases += 1
        was = self.xtts_loaded
        self.xtts_loaded = False
        return was

    def xtts_model_loaded(self):
        return self.xtts_loaded


class _FakeLLMGuardian:
    def __init__(self, running=None):
        self.running = running

    def running_model_info(self, model=None):
        return self.running

    def unload(self, model=None):
        return True


class ResourcePreflightTests(unittest.TestCase):
    @staticmethod
    def _snap(ram_pct, total=15.6, avail=5.33, vram=1911):
        return ResourceSnapshot(
            ram_used_pct=ram_pct,
            ram_total_gb=total,
            ram_available_gb=avail,
            vram_used_mb=vram,
            vram_total_mb=6141,
            vram_used_pct=100.0 * vram / 6141,
            gpu_name="RTX Test",
        )

    @staticmethod
    def _profile():
        return {
            "name": "voice-fast",
            "model": settings.LLM_VOICE_MODEL,
            "keep_alive": settings.DUAL_BRAIN_VOICE_KEEP_ALIVE,
            "num_ctx": settings.LLM_VOICE_NUM_CTX,
            "num_predict": settings.LLM_VOICE_NUM_PREDICT,
            "compact": True,
            "co_resident": True,
        }

    def test_preflight_releases_xtts_before_predicted_critical_voice_load(self):
        voice = _FakeVoice()
        guardian = ResourceGuardian(_FakeLLMGuardian(running=None), voice)
        profile = self._profile()
        samples = [self._snap(70.0, avail=4.68), self._snap(55.0, avail=7.0, vram=0)]
        with patch.object(guardian, "sample", side_effect=samples):
            guardian.prepare_for_llm(profile=profile)
        self.assertEqual(voice.xtts_releases, 1)
        self.assertFalse(profile["co_resident"])
        self.assertEqual(profile["keep_alive"], settings.RESOURCE_LLM_KEEP_ALIVE_VOICE)

    def test_preflight_keeps_xtts_when_predicted_ram_is_safe(self):
        voice = _FakeVoice()
        guardian = ResourceGuardian(_FakeLLMGuardian(running=None), voice)
        profile = self._profile()
        samples = [self._snap(57.9, avail=6.59), self._snap(57.9, avail=6.59)]
        with patch.object(guardian, "sample", side_effect=samples):
            guardian.prepare_for_llm(profile=profile)
        self.assertEqual(voice.xtts_releases, 0)
        self.assertTrue(profile["co_resident"])

    def test_preflight_does_not_add_cold_estimate_if_voice_model_already_resident(self):
        voice = _FakeVoice()
        guardian = ResourceGuardian(
            _FakeLLMGuardian(running={"name": settings.LLM_VOICE_MODEL, "size": 2_000_000_000, "size_vram": 2_000_000_000}),
            voice,
        )
        profile = self._profile()
        samples = [self._snap(84.0, avail=2.5), self._snap(84.0, avail=2.5)]
        with patch.object(guardian, "sample", side_effect=samples):
            guardian.prepare_for_llm(profile=profile)
        self.assertEqual(voice.xtts_releases, 0)
        self.assertTrue(profile["co_resident"])


class FinalizationIntegrationTests(unittest.TestCase):
    def test_dangling_neutron_sentence_is_completed_before_voice_output(self):
        original = "Les neutrons sont dans le noyau. Leur masse est proche de celle des protons ("
        final, triggered = finalize_voice_reply(
            original,
            output_tokens=128,
            num_predict=128,
            margin=4,
            done_reason="length",
            continuation="environ une unité de masse atomique).",
        )
        self.assertTrue(triggered)
        self.assertTrue(final.endswith("atomique)."))
        self.assertNotEqual(final[-1], "(")

    def test_failed_continuation_drops_only_dangling_fragment(self):
        original = "Première phrase complète. Une seconde information ("
        final, triggered = finalize_voice_reply(
            original,
            output_tokens=128,
            num_predict=128,
            done_reason="length",
            continuation="",
        )
        self.assertTrue(triggered)
        self.assertEqual(final, "Première phrase complète.")


if __name__ == "__main__":
    unittest.main()
