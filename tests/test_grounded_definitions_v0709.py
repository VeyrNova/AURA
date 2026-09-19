from regression_compat import assert_version_at_least
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from ai.knowledge_quality import (
    deterministic_knowledge_fallback,
    fail_closed_knowledge_sentence,
    find_knowledge_risks,
)
from ai.speech_quality import deterministic_french_fallback, find_voice_quality_issues
from config.settings import settings
from security.policy_engine import SecurityPolicyEngine
from tools.internet_manager import InternetToolManager
from tools.knowledge_reference import (
    KnowledgeReferenceTool,
    extract_definition_subject,
    local_reference,
)
from tools.models import ToolPlan
from tools.safe_http import HTTPResponse


class FakeHTTP:
    def __init__(self, payload):
        self.payload = payload
        self.urls = []

    def get_json(self, url, headers=None):
        self.urls.append(url)
        return self.payload, HTTPResponse(url, 200, "application/json", json.dumps(self.payload).encode("utf-8"))


class GroundedDefinitionTests(unittest.TestCase):
    QUESTION = "Explique-moi simplement ce qu'est un neutron"

    def test_version_and_safe_defaults(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.9")
        self.assertTrue(settings.KNOWLEDGE_REFERENCE_ENABLED)
        self.assertFalse(settings.LLM_VOICE_KNOWLEDGE_SELF_VERIFY)

    def test_exact_observed_question_extracts_neutron(self):
        self.assertEqual(extract_definition_subject(self.QUESTION), "neutron")
        self.assertEqual(extract_definition_subject("Qu'est-ce qu'un proton ?"), "proton")
        self.assertEqual(extract_definition_subject("C'est quoi un électron ?"), "électron")
        self.assertEqual(extract_definition_subject("Définis un atome."), "atome")
        self.assertEqual(extract_definition_subject("Pourquoi le ciel est bleu ?"), "")

    def test_local_neutron_reference_is_short_correct_french(self):
        card = local_reference("neutron")
        self.assertIsNotNone(card)
        text = " ".join(card)
        self.assertIn("sans charge électrique", text)
        self.assertIn("noyau", text)
        self.assertIn("proton", text)
        self.assertNotIn("nombre neutre", text)
        self.assertNotIn("d'une atomique", text)
        self.assertNotIn("électrons", card[-1])
        self.assertLessEqual(max(len(sentence) for sentence in card), 100)

    def test_planner_routes_neutron_before_llm_and_without_web(self):
        manager = InternetToolManager()
        # A pending weather context must not hijack a new definition topic.
        manager.context.state.tool = "weather"
        manager.context.state.category = "weather"
        manager.context.state.pending_slot = "location"
        manager.context.state.expires_at = manager.context._clock() + 60
        plan = manager.plan(self.QUESTION)
        self.assertIsNotNone(plan)
        self.assertEqual(plan.name, "knowledge_reference")
        self.assertEqual(plan.action, "KNOWLEDGE_REFERENCE_LOCAL")
        self.assertEqual(plan.args["subject"], "neutron")
        self.assertFalse(plan.args["allow_web"])
        self.assertFalse(manager.context.state.active)

    def test_local_reference_executes_without_network(self):
        fake = FakeHTTP({})
        tool = KnowledgeReferenceTool(fake)
        result = tool.execute("neutron", allow_web=True)
        self.assertTrue(result.ok)
        self.assertEqual(result.source, "aura-local-reference")
        self.assertEqual(fake.urls, [])
        self.assertTrue(result.response.startswith("Un neutron est"))

    def test_unknown_definition_uses_fixed_wikipedia_endpoint(self):
        fake = FakeHTTP({
            "query": {
                "pages": [{
                    "title": "Photosynthèse",
                    "extract": "La photosynthèse est un processus biologique. Elle permet à certains organismes de convertir l'énergie lumineuse. Une troisième phrase utile.",
                }]
            }
        })
        tool = KnowledgeReferenceTool(fake, max_sentences=2, max_chars=300)
        result = tool.execute("photosynthèse", allow_web=True)
        self.assertTrue(result.ok)
        self.assertEqual(result.source, "wikipedia-fr")
        self.assertEqual(len(fake.urls), 1)
        self.assertTrue(fake.urls[0].startswith("https://fr.wikipedia.org/w/api.php?"))
        self.assertNotIn("Une troisième phrase", result.response)
        self.assertIn("Source : Wikipédia", result.response)
        self.assertEqual(result.sources[0].host, "fr.wikipedia.org")

    def test_unknown_definition_fails_closed_when_web_disabled(self):
        result = KnowledgeReferenceTool(FakeHTTP({})).execute("terme inconnu", allow_web=False)
        self.assertFalse(result.ok)
        self.assertIn("Je préfère ne pas inventer", result.response)

    def test_security_distinguishes_local_and_web_reference(self):
        policy = SecurityPolicyEngine(db=None)
        self.assertTrue(policy.authorize("KNOWLEDGE_REFERENCE_LOCAL").allowed)
        self.assertTrue(policy.authorize("WEB_KNOWLEDGE_REFERENCE").allowed)


class ObservedFailureRegressionTests(unittest.TestCase):
    QUESTION = "Explique-moi simplement ce qu'est un neutron"
    BAD = "Le neutron est une particule subatomique qui constitue le noyau d'une atomique avec un nombre neutre, 0 ou un nombre entier positif, et est souvent associé à l'hydrogène."

    def test_observed_bad_french_is_detected(self):
        codes = {issue.code for issue in find_voice_quality_issues(self.BAD)}
        self.assertIn("dangling_science_adjective", codes)
        fixed = deterministic_french_fallback(self.BAD)
        self.assertNotIn("d'une atomique", fixed)
        self.assertIn("d'un atome", fixed)

    def test_observed_bad_definition_is_flagged(self):
        codes = {risk.code for risk in find_knowledge_risks(self.QUESTION, self.BAD)}
        self.assertIn("neutron_malformed_definition", codes)
        fixed = deterministic_knowledge_fallback(self.BAD, self.QUESTION)
        self.assertIn("sans charge électrique", fixed)
        self.assertIn("noyau", fixed)
        self.assertNotIn("nombre neutre", fixed)

    def test_fail_closed_sentence_contains_no_new_fact(self):
        fallback = fail_closed_knowledge_sentence()
        self.assertIn("source fiable", fallback)
        self.assertNotIn("neutron", fallback.casefold())

    def test_main_window_cannot_accept_flagged_fact_with_plain_ok_by_default(self):
        source = (Path(__file__).resolve().parents[1] / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("LLM_VOICE_KNOWLEDGE_SELF_VERIFY", source)
        self.assertIn("knowledge-quality FAIL-CLOSED", source)
        self.assertNotIn('if candidate.casefold() == "ok"', source)


if __name__ == "__main__":
    unittest.main()
