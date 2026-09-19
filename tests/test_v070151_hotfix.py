from regression_compat import assert_version_at_least
import unittest
from unittest.mock import patch

from config.settings import settings
from runtime.resource_guardian import ResourceGuardian, ResourceSnapshot
from tools.internet_manager import InternetToolManager
from tools.knowledge_reference import extract_explanation_subject, local_reference
from voice.xtts_tts import XTTSTTS


class _PrewarmLLM:
    pass


class _PrewarmVoice:
    def __init__(self):
        self.loaded = False
        self.warmups = 0
        self.releases = 0

    def xtts_model_loaded(self):
        return self.loaded

    def warmup_xtts_only(self):
        self.warmups += 1
        self.loaded = True
        return True

    def release_xtts_model(self):
        self.releases += 1
        self.loaded = False
        return True


class V070151RoutingTests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.15.6.10")

    def test_sky_explanation_is_groundable(self):
        subject = extract_explanation_subject("Pourquoi le ciel est bleu ?")
        self.assertEqual(subject, "le ciel est bleu")
        card = local_reference(subject)
        self.assertIsNotNone(card)
        self.assertIn("Rayleigh", " ".join(card))

    def test_personal_why_is_not_forced_into_reference_tool(self):
        self.assertEqual(extract_explanation_subject("Pourquoi tu me dis ça ?"), "")

    def test_factual_explanation_is_planned_before_llm(self):
        manager = InternetToolManager()
        plan = manager.plan("Pourquoi le ciel est bleu ?")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.name, "knowledge_reference")
        self.assertEqual(plan.action, "KNOWLEDGE_REFERENCE_LOCAL")

    def test_bare_search_verb_is_not_sent_to_llm(self):
        # Patch 26.6: an explicit research verb is now a hard Web-search
        # contract. It must never silently substitute Wikipedia/reference mode.
        manager = InternetToolManager()
        with patch.object(settings, "BRAVE_SEARCH_API_KEY", ""), \
             patch.object(settings, "WEB_SEARCH_ENABLED", True), \
             patch.object(settings, "KNOWLEDGE_REFERENCE_WEB_ENABLED", True):
            plan = manager.plan("cherche qui a écrit les misérables")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.name, "web_search")
        self.assertEqual(plan.action, "WEB_SEARCH")
        self.assertTrue(plan.args.get("explicit_research"))

    def test_broad_bare_search_uses_real_search_provider(self):
        manager = InternetToolManager()
        with patch.object(settings, "BRAVE_SEARCH_API_KEY", ""), patch.object(settings, "WEB_SEARCH_ENABLED", True):
            plan = manager.plan("cherche 5 destinations intéressantes autour de Nice avec leurs avantages")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.name, "web_search")


class V070151PrewarmTests(unittest.TestCase):
    @staticmethod
    def _snap(ram, avail, vram_used=0.0):
        return ResourceSnapshot(
            ram_used_pct=ram,
            ram_total_gb=16.0,
            ram_available_gb=avail,
            vram_used_mb=vram_used,
            vram_total_mb=6141.0,
            vram_used_pct=(100.0 * vram_used / 6141.0 if vram_used else 0.0),
            gpu_name="RTX Test",
        )

    def test_xtts_prewarm_allows_67_percent_when_headroom_is_good(self):
        voice = _PrewarmVoice()
        guardian = ResourceGuardian(_PrewarmLLM(), voice)
        before = self._snap(67.4, 5.13, 0.0)
        after = self._snap(75.0, 3.9, 1911.0)
        with patch.object(settings, "XTTS_DEVICE", "cuda"), \
             patch.object(settings, "XTTS_ALLOW_CUDA", True), \
             patch.object(settings, "XTTS_CUDA_DISPLAY_MIN_VRAM_MB", 0), \
             patch.object(settings, "XTTS_PREWARM_MIN_AVAILABLE_RAM_GB", 3.5), \
             patch.object(settings, "XTTS_PREWARM_MAX_RAM_PCT", 86.0), \
             patch.object(settings, "XTTS_PREWARM_POSTLOAD_MAX_RAM_PCT", 91.0), \
             patch.object(guardian, "dual_brain_co_resident_ready", return_value=True), \
             patch.object(guardian, "sample", side_effect=[before, after]), \
             patch.object(guardian, "_xtts_estimate_mb", return_value=1911.0):
            self.assertTrue(guardian.conditional_xtts_prewarm())
        self.assertEqual(voice.warmups, 1)
        self.assertEqual(voice.releases, 0)

    def test_xtts_prewarm_refuses_low_available_ram_even_under_percent_cap(self):
        voice = _PrewarmVoice()
        guardian = ResourceGuardian(_PrewarmLLM(), voice)
        before = self._snap(78.0, 2.5, 0.0)
        with patch.object(settings, "XTTS_DEVICE", "cuda"), \
             patch.object(settings, "XTTS_ALLOW_CUDA", True), \
             patch.object(settings, "XTTS_CUDA_DISPLAY_MIN_VRAM_MB", 0), \
             patch.object(settings, "XTTS_PREWARM_MIN_AVAILABLE_RAM_GB", 3.5), \
             patch.object(settings, "XTTS_PREWARM_MAX_RAM_PCT", 86.0), \
             patch.object(guardian, "dual_brain_co_resident_ready", return_value=True), \
             patch.object(guardian, "sample", return_value=before), \
             patch.object(guardian, "_xtts_estimate_mb", return_value=1911.0):
            self.assertFalse(guardian.conditional_xtts_prewarm())
        self.assertEqual(voice.warmups, 0)


class V070151SpeechChunkTests(unittest.TestCase):
    def test_short_multi_sentence_weather_starts_with_first_sentence(self):
        text = (
            "À Vidauban, 22 virgule 6 degrés, partiellement nuageux. "
            "Vent 4 kilomètres par heure. Pas de pluie actuellement"
        )
        plan = XTTSTTS._natural_chunk_plan(
            text,
            first_limit=120,
            next_limit=170,
            min_chars=48,
            max_chunks=8,
        )
        self.assertGreaterEqual(len(plan), 2)
        self.assertEqual(plan[0].boundary, "sentence")
        self.assertIn("partiellement nuageux", plan[0].text)
        self.assertLess(len(plan[0].text), len(text))
        self.assertEqual(" ".join(chunk.text for chunk in plan), text)


if __name__ == "__main__":
    unittest.main()
