import unittest
from datetime import datetime, timezone

from consciousness.context_builder import ConsciousnessContextBuilder
from consciousness.self_model import CapabilityState, SelfModel
from grounding.manager import GroundedIntelligence


class GroundedIntelligenceV066Tests(unittest.TestCase):
    def setUp(self):
        self.guard = GroundedIntelligence()
        self.offline = SelfModel(CapabilityState(internet=False))
        self.online = SelfModel(CapabilityState(internet=True))

    def test_weather_is_blocked_without_live_source(self):
        d = self.guard.evaluate("Quelle météo fait-il aujourd'hui ?", self.offline)
        self.assertTrue(d.handled)
        self.assertEqual(d.category, "weather")
        self.assertIn("temps réel", d.response)
        self.assertIn("ne pas inventer", d.response)

    def test_news_finance_sports_and_traffic_are_grounded(self):
        for text, category in (
            ("Quelles sont les actualités du jour ?", "news"),
            ("Quel est le prix actuel du bitcoin ?", "finance"),
            ("Quel est le score du match ce soir ?", "sports"),
            ("Y a-t-il des bouchons maintenant ?", "traffic"),
        ):
            with self.subTest(text=text):
                d = self.guard.evaluate(text, self.offline)
                self.assertTrue(d.handled)
                self.assertEqual(d.category, category)

    def test_local_clock_is_a_trusted_local_source(self):
        now = datetime(2026, 8, 8, 11, 7, tzinfo=timezone.utc)
        d = self.guard.evaluate("Quelle heure est-il ?", self.offline, now=now)
        self.assertTrue(d.handled)
        self.assertEqual(d.source, "system_clock")
        self.assertIn("11:07", d.response)

    def test_static_question_is_not_overblocked(self):
        self.assertFalse(self.guard.evaluate("Pourquoi le ciel est-il bleu ?", self.offline).handled)
        self.assertFalse(self.guard.evaluate("J'ai acheté des bouchons en liège.", self.offline).handled)

    def test_live_requests_fail_closed_if_tool_layer_did_not_handle_them(self):
        d = self.guard.evaluate("Quelle météo fait-il aujourd'hui ?", self.online)
        self.assertTrue(d.handled)
        self.assertEqual(d.category, "weather")

    def test_prompt_contains_explicit_grounding_rules(self):
        prompt = ConsciousnessContextBuilder(self_model=self.offline).build_system_prompt(compact=True)
        self.assertIn("Meteo, actualites, cours, trafic", prompt)
        self.assertIn("N'invente jamais une meteo", prompt)


if __name__ == "__main__":
    unittest.main()
