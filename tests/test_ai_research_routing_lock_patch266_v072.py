from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from config.settings import settings
from tools.internet_manager import InternetToolManager
from tools.search_intent import extract_explicit_search_query, is_explicit_search_request


class Patch266ResearchLanguageTests(unittest.TestCase):
    CASES = {
        "Aura, recherche-moi 5 destinations autour de Nice": "5 destinations autour de Nice",
        "cherche sur internet nouveautés Python": "nouveautés Python",
        "fais des recherches sur les meilleurs modèles IA locaux": "les meilleurs modèles IA locaux",
        "fais-moi une recherche sur les hôtels à Nice": "les hôtels à Nice",
        "peux-tu faire une recherche sur les dernières nouveautés de Python": "les dernières nouveautés de Python",
        "Pourrais tu faire des recherches sur les prix des SSD ?": "les prix des SSD",
        "tu peux rechercher les sorties Deftones récentes ?": "les sorties Deftones récentes",
        "va chercher les dernières actualités IA": "les dernières actualités IA",
        "vas vérifier sur internet si cette information est vraie": "si cette information est vraie",
        "je veux que tu recherches les meilleurs restaurants à Toulon": "les meilleurs restaurants à Toulon",
        "j’aimerais que tu recherches des infos sur AURA": "des infos sur AURA",
    }

    def test_natural_research_phrasings_are_explicit(self):
        for text, expected in self.CASES.items():
            with self.subTest(text=text):
                self.assertTrue(is_explicit_search_request(text))
                self.assertEqual(extract_explicit_search_query(text), expected)

    def test_normal_factual_question_is_not_forced_to_search(self):
        for text in ("Qui est Victor Hugo ?", "Pourquoi le ciel est bleu ?", "Peux-tu m'expliquer Victor Hugo ?"):
            with self.subTest(text=text):
                self.assertFalse(is_explicit_search_request(text))


class Patch266ResearchPlannerTests(unittest.TestCase):
    def test_explicit_research_preempts_knowledge_reference(self):
        manager = InternetToolManager()
        with patch.object(settings, "GEMINI_API_KEY", ""), \
             patch.object(settings, "WEB_SEARCH_ENABLED", True), \
             patch.object(settings, "KNOWLEDGE_REFERENCE_ENABLED", True), \
             patch.object(settings, "KNOWLEDGE_REFERENCE_WEB_ENABLED", True):
            plan = manager.plan("cherche qui a écrit les misérables")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.name, "web_search")
        self.assertEqual(plan.action, "WEB_SEARCH")
        self.assertTrue(plan.args.get("explicit_research"))
        self.assertEqual(plan.args.get("engine"), "free-web-search")

    def test_explicit_research_plan_survives_global_internet_disabled(self):
        manager = InternetToolManager()
        with patch.object(settings, "INTERNET_TOOLS_ENABLED", False):
            plan = manager.plan("fais des recherches sur les nouveautés IA")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.name, "web_search")
        self.assertTrue(plan.args.get("explicit_research"))

    def test_explicit_research_plan_survives_web_search_disabled(self):
        manager = InternetToolManager()
        with patch.object(settings, "WEB_SEARCH_ENABLED", False):
            plan = manager.plan("peux-tu faire une recherche sur Python 3")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.name, "web_search")

    def test_disabled_engine_fails_closed_instead_of_falling_back_to_llm(self):
        manager = InternetToolManager()
        plan = manager.plan("fais des recherches sur les nouveautés IA")
        with patch.object(settings, "INTERNET_TOOLS_ENABLED", False):
            result = manager.execute(plan)
        self.assertFalse(result.ok)
        self.assertEqual(result.category, "web_search")
        self.assertEqual(result.source, "research_engine_disabled")
        self.assertIn("réponse inventée", result.response)

    def test_missing_provider_fails_closed(self):
        manager = InternetToolManager()
        with patch.object(settings, "INTERNET_TOOLS_ENABLED", True), \
             patch.object(settings, "WEB_SEARCH_ENABLED", True), \
             patch("tools.web_search.ddgs_available", return_value=False):
            plan = manager.plan("recherche-moi les dernières nouveautés Python")
            result = manager.execute(plan)
        self.assertFalse(result.ok)
        self.assertEqual(result.source, "dependency_missing")
        self.assertEqual(result.category, "web_search")

    def test_non_explicit_definition_keeps_reference_route(self):
        manager = InternetToolManager()
        plan = manager.plan("Pourquoi le ciel est bleu ?")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.name, "knowledge_reference")


class Patch266UiInvariantTests(unittest.TestCase):
    def test_ui_intercepts_research_before_agent_kernel(self):
        source = Path(__file__).resolve().parents[1].joinpath("ui", "main_window.py").read_text(encoding="utf-8")
        research = source.index("if is_explicit_search_request(text):")
        agent = source.index("agent_plan = self.aura_core.plan_agent_task(text)", research)
        self.assertLess(research, agent)
        self.assertIn("Explicit research route=ai-search-engine", source[research:agent])


if __name__ == "__main__":
    unittest.main()
