from regression_compat import assert_version_at_least
import unittest
from pathlib import Path

from ai.knowledge_quality import (
    deterministic_knowledge_fallback,
    find_knowledge_risks,
    knowledge_candidate_is_safe,
    knowledge_verification_messages,
)
from ai.llm_manager import OllamaProvider
from ai.voice_brevity import (
    apply_voice_output_contract,
    is_factual_explanation_request,
    trim_spoken_reply,
    voice_brevity_policy,
    voice_output_contract,
)
from config.settings import settings
from runtime.resource_guardian import ResourceGuardian, ResourceSnapshot


class _Voice:
    def xtts_model_loaded(self):
        return True

    def release_xtts_model(self):
        return True

    def release_stt_model(self):
        return True


class _LLM:
    def model_available(self, model):
        return True

    def running_model_info(self, model=None):
        return None

    def running_model_query_ok(self):
        return True


class VoiceBrevityTests(unittest.TestCase):
    def test_version_and_defaults(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.9")
        self.assertEqual(settings.LLM_VOICE_MAX_SENTENCES, 3)
        self.assertEqual(settings.LLM_VOICE_FIRST_SENTENCE_TARGET, 85)
        self.assertLess(settings.LLM_VOICE_TEMPERATURE, settings.LLM_TEMPERATURE)
        self.assertLess(settings.LLM_VOICE_NUM_PREDICT, 128)
        self.assertTrue(settings.LLM_VOICE_KNOWLEDGE_GATE)

    def test_simple_explanation_is_factual(self):
        self.assertTrue(is_factual_explanation_request("Explique-moi simplement ce qu'est un neutron"))
        self.assertTrue(is_factual_explanation_request("C'est quoi un proton ?"))

    def test_live_question_is_not_local_knowledge_gate(self):
        self.assertFalse(is_factual_explanation_request("Explique-moi la météo actuelle à Paris"))

    def test_detail_request_gets_larger_budget(self):
        normal = voice_brevity_policy("Explique-moi un neutron")
        detailed = voice_brevity_policy("Explique-moi en détail un neutron")
        self.assertFalse(normal.detailed)
        self.assertTrue(detailed.detailed)
        self.assertGreater(detailed.max_sentences, normal.max_sentences)
        self.assertGreater(detailed.max_chars, normal.max_chars)

    def test_contract_explicitly_targets_short_first_sentence(self):
        policy = voice_brevity_policy("Explique-moi un neutron", first_sentence_target=85)
        contract = voice_output_contract(policy)
        self.assertIn("2 à 3 phrases", contract)
        self.assertIn("85 caractères", contract)
        self.assertIn("définition essentielle", contract)

    def test_contract_is_appended_to_system_message(self):
        policy = voice_brevity_policy("Explique-moi un neutron")
        messages = [{"role": "system", "content": "BASE"}, {"role": "user", "content": "Question"}]
        result = apply_voice_output_contract(messages, policy)
        self.assertIn("BASE", result[0]["content"])
        self.assertIn("VOICE OUTPUT CONTRACT v0.7.0.14", result[0]["content"])
        self.assertEqual(messages[0]["content"], "BASE")

    def test_trim_keeps_only_complete_sentences(self):
        policy = voice_brevity_policy("Explique-moi un neutron", max_sentences=3, max_chars=320)
        text = (
            "Un neutron est une particule sans charge électrique. "
            "Sa masse est proche de celle d'un proton. "
            "Il se trouve dans le noyau atomique. "
            "Cette quatrième phrase doit disparaître."
        )
        trimmed, changed = trim_spoken_reply(text, policy)
        self.assertTrue(changed)
        self.assertNotIn("quatrième", trimmed)
        self.assertTrue(trimmed.endswith("."))

    def test_trim_never_cuts_first_sentence_midway(self):
        policy = voice_brevity_policy("Explique-moi un neutron", max_chars=80)
        text = "Cette première phrase est volontairement assez longue pour dépasser le budget mais elle doit rester entière. Une autre phrase."
        trimmed, changed = trim_spoken_reply(text, policy)
        self.assertTrue(changed)
        self.assertTrue(trimmed.endswith("entière."))


class KnowledgeQualityTests(unittest.TestCase):
    QUESTION = "Explique-moi simplement ce qu'est un neutron"

    def test_observed_neutron_mass_error_is_detected(self):
        bad = "Il possède une masse similaire à celle des protons et des électrons."
        codes = {risk.code for risk in find_knowledge_risks(self.QUESTION, bad)}
        self.assertIn("neutron_mass_electron", codes)

    def test_known_neutron_error_has_deterministic_fix(self):
        bad = "Le neutron possède une masse similaire à celle des protons et des électrons."
        fixed = deterministic_knowledge_fallback(bad, self.QUESTION)
        self.assertIn("proton", fixed)
        self.assertNotIn("électrons", fixed)
        self.assertEqual(find_knowledge_risks(self.QUESTION, fixed), ())

    def test_correct_neutron_sentence_does_not_trigger_known_error(self):
        good = "Le neutron n'a pas de charge électrique, et sa masse est proche de celle d'un proton."
        self.assertEqual(find_knowledge_risks(self.QUESTION, good), ())

    def test_generic_science_compound_comparison_is_flagged_for_self_check(self):
        text = "Cette molécule a une énergie similaire à celle des atomes et des électrons."
        codes = {risk.code for risk in find_knowledge_risks("Explique-moi cette molécule", text)}
        self.assertIn("compound_science_comparison", codes)

    def test_nonfactual_chat_never_triggers_knowledge_gate(self):
        text = "Le neutron a une masse similaire à celle des protons et des électrons."
        self.assertEqual(find_knowledge_risks("Raconte-moi une blague", text), ())

    def test_verifier_prompt_is_narrow_and_static(self):
        messages = knowledge_verification_messages(self.QUESTION, "Phrase test.")
        self.assertEqual(len(messages), 2)
        self.assertIn("UNE phrase", messages[0]["content"])
        self.assertIn("connaissance générale stable", messages[0]["content"])
        self.assertIn("temps réel", messages[0]["content"])

    def test_candidate_rejects_number_changes(self):
        original = "La particule a une masse de 10 unités."
        candidate = "La particule a une masse de 20 unités."
        self.assertFalse(knowledge_candidate_is_safe(original, candidate))


class VoiceSamplingProfileTests(unittest.TestCase):
    @staticmethod
    def snap():
        return ResourceSnapshot(
            ram_used_pct=55.0,
            ram_total_gb=15.6,
            ram_available_gb=7.0,
            vram_used_mb=1911,
            vram_total_mb=6141,
            vram_used_pct=31.1,
            gpu_name="test",
        )

    def test_voice_profile_carries_low_sampling_values(self):
        guardian = ResourceGuardian(_LLM(), _Voice())
        guardian.sample = lambda force_gpu=False: self.snap()
        guardian.dual_brain_co_resident_ready = lambda snapshot=None: True
        profile = guardian.llm_request_profile(voice_output=True)
        self.assertEqual(profile["temperature"], settings.LLM_VOICE_TEMPERATURE)
        self.assertEqual(profile["top_p"], settings.LLM_VOICE_TOP_P)
        self.assertEqual(profile["num_predict"], settings.LLM_VOICE_NUM_PREDICT)

    def test_ollama_payload_accepts_sampling_override(self):
        provider = OllamaProvider("http://localhost:11434", "llama3.1")
        payload = provider._payload(
            [{"role": "user", "content": "test"}],
            stream=False,
            temperature=0.12,
            top_p=0.66,
            num_predict=104,
        )
        self.assertAlmostEqual(payload["options"]["temperature"], 0.12)
        self.assertAlmostEqual(payload["options"]["top_p"], 0.66)
        self.assertEqual(payload["options"]["num_predict"], 104)

    def test_main_window_wires_brevity_and_knowledge_without_qt_import(self):
        source = (Path(__file__).resolve().parents[1] / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("apply_voice_output_contract", source)
        self.assertIn("find_knowledge_risks", source)
        self.assertIn("trim_spoken_reply", source)
        self.assertIn("temperature=profile.get(\"temperature\")", source)


if __name__ == "__main__":
    unittest.main()
