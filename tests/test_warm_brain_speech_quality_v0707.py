from regression_compat import assert_version_at_least
import unittest
from pathlib import Path
from unittest.mock import patch

from ai.speech_quality import (
    correction_is_safe,
    deterministic_french_fallback,
    find_voice_quality_issues,
    quality_correction_messages,
    split_spoken_sentences,
)
from config.settings import settings
from runtime.resource_guardian import ResourceGuardian, ResourceSnapshot
from voice.xtts_tts import XTTSTTS


class FakeVoice:
    def __init__(self, loaded=True):
        self.loaded = loaded
        self.releases = 0

    def xtts_model_loaded(self):
        return self.loaded

    def release_xtts_model(self):
        self.releases += 1
        was = self.loaded
        self.loaded = False
        return was

    def release_stt_model(self):
        return True


class FakeLLM:
    def __init__(self, *, resident=False, available=True):
        self.resident = resident
        self.available = available
        self.warmups = []
        self.unloads = []
        self.query_ok = True

    def model_available(self, model):
        return self.available and str(model).casefold() == settings.LLM_VOICE_MODEL.casefold()

    def running_model_info(self, model=None):
        if self.resident and str(model or settings.LLM_VOICE_MODEL).casefold() == settings.LLM_VOICE_MODEL.casefold():
            return {"name": settings.LLM_VOICE_MODEL, "size": 2_000_000_000, "size_vram": 600_000_000}
        return None

    def running_model_query_ok(self):
        return self.query_ok

    def warmup(self, **kwargs):
        self.warmups.append(dict(kwargs))
        self.resident = True

    def unload(self, model=None):
        self.unloads.append(model)
        if str(model).casefold() == settings.LLM_VOICE_MODEL.casefold():
            self.resident = False
        return True


class WarmBrainTests(unittest.TestCase):
    @staticmethod
    def snap(ram, avail, used=1911):
        return ResourceSnapshot(
            ram_used_pct=float(ram),
            ram_total_gb=15.6,
            ram_available_gb=float(avail),
            vram_used_mb=float(used),
            vram_total_mb=6141.0,
            vram_used_pct=100.0 * float(used) / 6141.0,
            gpu_name="RTX Test",
        )

    def test_version_and_new_defaults(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.7")
        self.assertTrue(settings.VOICE_BRAIN_POST_START_PREWARM)
        self.assertLess(settings.VOICE_BRAIN_PREWARM_MAX_RAM_PCT, settings.RESOURCE_RAM_CRITICAL_PCT)
        self.assertTrue(settings.LLM_VOICE_QUALITY_GATE)
        self.assertGreaterEqual(settings.FAST_SPEECH_MAX_SENTENCE_CHARS, 160)

    def test_safe_post_start_prewarm_keeps_xtts_hot(self):
        llm = FakeLLM()
        voice = FakeVoice(loaded=True)
        guardian = ResourceGuardian(llm, voice, clock=lambda: 100.0)
        with patch.object(guardian, "dual_brain_co_resident_ready", return_value=True), patch.object(
            guardian, "sample", side_effect=[self.snap(55.6, 6.95), self.snap(81.9, 2.82)]
        ), patch("runtime.resource_guardian.settings.XTTS_CUDA_DISPLAY_MIN_VRAM_MB", 4096):
            self.assertTrue(guardian.conditional_voice_llm_prewarm())
        self.assertEqual(len(llm.warmups), 1)
        self.assertTrue(llm.resident)
        self.assertTrue(voice.loaded)
        self.assertEqual(voice.releases, 0)
        self.assertEqual(guardian._voice_llm_prewarm_last_result, "loaded")
        self.assertTrue(guardian._last_llm_profile.get("co_resident"))

    def test_prewarm_refuses_unsafe_predicted_ram(self):
        llm = FakeLLM()
        voice = FakeVoice(loaded=True)
        guardian = ResourceGuardian(llm, voice)
        with patch.object(guardian, "dual_brain_co_resident_ready", return_value=True), patch.object(
            guardian, "sample", return_value=self.snap(70.0, 4.68)
        ):
            self.assertFalse(guardian.conditional_voice_llm_prewarm())
        self.assertEqual(llm.warmups, [])
        self.assertTrue(voice.loaded)
        self.assertEqual(guardian._voice_llm_prewarm_last_result, "ram-headroom")

    def test_prewarm_rolls_voice_brain_back_if_postload_ram_is_critical(self):
        llm = FakeLLM()
        voice = FakeVoice(loaded=True)
        guardian = ResourceGuardian(llm, voice, clock=lambda: 100.0)
        with patch.object(guardian, "dual_brain_co_resident_ready", return_value=True), patch.object(
            guardian, "sample", side_effect=[self.snap(55.0, 7.02), self.snap(95.0, 0.78)]
        ), patch.object(guardian, "_wait_model_unloaded", return_value=True):
            self.assertFalse(guardian.conditional_voice_llm_prewarm())
        self.assertFalse(llm.resident)
        self.assertTrue(voice.loaded)
        self.assertEqual(voice.releases, 0)
        self.assertEqual(guardian._voice_llm_prewarm_last_result, "released-after-pressure")

    def test_user_cancel_prevents_scheduled_prewarm(self):
        llm = FakeLLM()
        guardian = ResourceGuardian(llm, FakeVoice(loaded=True))
        guardian.request_voice_llm_prewarm_cancel()
        self.assertFalse(guardian.conditional_voice_llm_prewarm())
        self.assertEqual(llm.warmups, [])
        self.assertEqual(guardian._voice_llm_prewarm_last_result, "cancelled-before-start")


class WarmBrainUiWiringTests(unittest.TestCase):
    def test_post_start_prewarm_is_scheduled_after_startup_ready(self):
        source = (Path(__file__).resolve().parents[1] / "ui" / "main_window.py").read_text(encoding="utf-8")
        start = source.index("def _cleanup_warmup_thread")
        end = source.index("def _start_voice_brain_prewarm", start)
        block = source[start:end]
        self.assertIn("self.startup_ready.emit()", block)
        self.assertEqual(block.count("self.startup_ready.emit()"), 1)
        self.assertIn("self._start_voice_brain_prewarm", block)
        self.assertLess(block.index("self.startup_ready.emit()"), block.index("self._start_voice_brain_prewarm"))

    def test_user_message_can_cancel_or_defer_background_prewarm(self):
        source = (Path(__file__).resolve().parents[1] / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("def _defer_message_for_voice_brain_prewarm", source)
        self.assertIn("request_voice_llm_prewarm_cancel", source)
        self.assertIn("if self._defer_message_for_voice_brain_prewarm(text):", source)


class FrenchSpeechQualityTests(unittest.TestCase):
    def test_detects_observed_structure_agreement_error(self):
        text = "Les neutrons jouent un rôle essentiel dans la structure stables des noyaux."
        issues = find_voice_quality_issues(text)
        self.assertIn("structure_agreement", {issue.code for issue in issues})

    def test_detects_observed_article_plural_error(self):
        issues = find_voice_quality_issues("Un neutron se trouve au cœur du noyau d'une atomes.")
        self.assertIn("article_plural_science", {issue.code for issue in issues})

    def test_correct_science_sentence_does_not_trigger_gate(self):
        text = "Un neutron est une particule subatomique qui compose les noyaux des atomes."
        self.assertEqual(find_voice_quality_issues(text), ())

    def test_deterministic_fallback_fixes_logged_errors(self):
        self.assertEqual(
            deterministic_french_fallback("La structure stables des noyaux est importante."),
            "La structure stable des noyaux est importante.",
        )
        self.assertIn("des atomes", deterministic_french_fallback("au cœur du noyau d'une atomes."))

    def test_quality_correction_rejects_changed_number(self):
        original = "La température est de 36,5 degrés Celsius."
        candidate = "La température est de 26,5 degrés Celsius."
        self.assertFalse(correction_is_safe(original, candidate))

    def test_quality_correction_prompt_forbids_factual_changes(self):
        messages = quality_correction_messages("La structure stables des noyaux est importante.")
        self.assertEqual(len(messages), 2)
        self.assertIn("Ne change aucun fait", messages[0]["content"])
        self.assertIn("Renvoie uniquement la phrase corrigée", messages[0]["content"])

    def test_sentence_split_preserves_three_sentences(self):
        parts = split_spoken_sentences("Une phrase. Une autre ! Et la dernière ?")
        self.assertEqual(len(parts), 3)
        self.assertTrue(parts[0].endswith("."))
        self.assertTrue(parts[1].endswith("!"))
        self.assertTrue(parts[2].endswith("?"))


class LongSentenceProsodyTests(unittest.TestCase):
    def test_logged_210_char_sentence_splits_on_natural_clause(self):
        text = (
            "Les neutrons jouent un rôle essentiel dans la structure stable des noyaux, "
            "car ils maintiennent l'équilibre entre les charges positives des protons "
            "et les forces électromagnétiques entre les protons eux-mêmes."
        )
        self.assertGreater(len(text), settings.FAST_SPEECH_MAX_SENTENCE_CHARS)
        plan = XTTSTTS._natural_chunk_plan(
            text,
            first_limit=120,
            next_limit=170,
            min_chars=48,
            max_chunks=8,
        )
        self.assertGreaterEqual(len(plan), 2)
        self.assertLessEqual(max(len(chunk.text) for chunk in plan), settings.FAST_SPEECH_MAX_SENTENCE_CHARS)
        self.assertIn(plan[0].boundary, {"clause", "conjunction"})
        self.assertNotEqual(plan[0].boundary, "fallback")

    def test_normal_sentence_under_cap_stays_whole(self):
        text = (
            "Cette phrase reste suffisamment courte pour être synthétisée d'un seul bloc, "
            "sans perdre sa prosodie naturelle."
        )
        plan = XTTSTTS._natural_chunk_plan(
            text,
            first_limit=120,
            next_limit=170,
            min_chars=48,
            max_chunks=8,
        )
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0].text, text)


if __name__ == "__main__":
    unittest.main()
