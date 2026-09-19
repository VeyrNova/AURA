import unittest
from unittest.mock import patch

from core.intent_manager import IntentManager
from tools.geo_resolver import resolve_geo_entity, canonical_geo_query
from tools.internet_manager import InternetToolManager
from voice.text_to_speech import sanitize_for_speech
from ui.response_presentation import for_tool_result
from tools.models import ToolPlan, ToolResult


class FrenchGeoJarvisV071366Tests(unittest.TestCase):
    def test_aura_first_person_feminine_agreement(self):
        self.assertEqual(sanitize_for_speech("Je suis prêt."), "je suis prête.")
        self.assertEqual(sanitize_for_speech("Je suis connecté et prêt."), "je suis connectée et prête.")
        self.assertEqual(sanitize_for_speech("Le système est prêt."), "Le système est prêt.")

    def test_geo_alias_new_york_variants(self):
        for value in ("new-york", "new york", "NewYork", "NYC"):
            entity = resolve_geo_entity(value)
            self.assertEqual(entity.canonical, "New York")
            self.assertEqual(entity.kind, "city")
            self.assertTrue(entity.matched_alias)

    def test_geo_region_and_country_aliases(self):
        self.assertEqual(canonical_geo_query("paca"), "Provence-Alpes-Côte d'Azur")
        self.assertEqual(canonical_geo_query("etats unis"), "États-Unis")

    def test_unknown_city_is_safely_canonicalized(self):
        entity = resolve_geo_entity("saint-raphael")
        self.assertEqual(entity.canonical, "Saint Raphael")
        self.assertFalse(entity.matched_alias)

    def test_natural_local_listing_phrases_stay_deterministic(self):
        manager = IntentManager()
        self.assertEqual(manager.detect("affiche mes tâches")[0], "LIST_TASKS")
        self.assertEqual(manager.detect("ouvre mes notes")[0], "LIST_NOTES")
        self.assertEqual(manager.detect("affiche mes rappels")[0], "LIST_REMINDERS")

    def test_weather_plan_canonicalizes_geo_alias(self):
        manager = InternetToolManager()
        plan = manager.plan("quelle météo à new-york ?")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.name, "weather")
        self.assertEqual(plan.args["location"], "New York")

    def test_knowledge_reference_is_visual_first(self):
        result = ToolResult(True, "Une information courte.", "knowledge_reference", "local")
        plan = ToolPlan("knowledge_reference", "KNOWLEDGE_REFERENCE_LOCAL", {"subject": "Mars"}, "knowledge_reference")
        decision = for_tool_result(result, plan)
        self.assertTrue(decision.visual)
        self.assertIn("INFORMATIONS", decision.title)
        self.assertIn("affiche", decision.speech)


if __name__ == "__main__":
    unittest.main()
