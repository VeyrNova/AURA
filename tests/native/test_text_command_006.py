import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from aura_native.reminders.temporal_fr import parse_french_temporal
from aura_native.intents.router import NativeIntentRouter

NOW = datetime(2026, 10, 10, 14, 0, tzinfo=ZoneInfo('Europe/Paris'))

class TextCommand006Tests(unittest.TestCase):
    def test_absolute_forms(self):
        for phrase, expected in [('15 octobre à 14h','2026-10-15T14:00'),('15 octobre à 14h30','2026-10-15T14:30'),('15/10 à 14h','2026-10-15T14:00'),('15/10/2026 à 14h','2026-10-15T14:00'),('15-10-2026 à 14h','2026-10-15T14:00')]:
            self.assertEqual(parse_french_temporal(phrase, now=NOW).trigger_at, expected)
    def test_relative_forms(self):
        expected = [('dans 20 minutes','14:20'),('dans 1 heure','15:00'),('dans 2 heures','16:00'),('dans 1 jour','2026-10-11T14:00'),('dans 3 jours','2026-10-13T14:00'),('dans une semaine','2026-10-17T14:00'),('dans 2 semaines','2026-10-24T14:00')]
        for phrase, suffix in expected:
            self.assertTrue(parse_french_temporal(phrase, now=NOW).trigger_at.endswith(suffix))
    def test_days_weekdays_and_dayparts(self):
        for phrase in ('aujourd’hui à 15h','demain à 15h','après-demain à 15h','lundi à 9h','lundi prochain à 9h','demain matin','demain après-midi','demain soir'):
            self.assertEqual(parse_french_temporal(phrase, now=NOW).status, 'OK')
        self.assertEqual(parse_french_temporal('ce matin', now=NOW).status, 'INVALID_PAST_TIME')
    def test_invalid_and_recurrence(self):
        for phrase in ('31 février à 14h','25:99','demain'):
            self.assertIn(parse_french_temporal(phrase, now=NOW).status, ('INVALID_DATE','NEEDS_TIME'))
        self.assertEqual(parse_french_temporal('tous les lundis à 8h', now=NOW).status, 'UNSUPPORTED_RECURRENCE')
        self.assertEqual(parse_french_temporal('aujourd’hui à 13h', now=NOW).status, 'INVALID_PAST_TIME')
    def test_router_local_search_and_web(self):
        router=NativeIntentRouter()
        self.assertEqual(router.parse('cherche dans mes notes projet').intent, 'SEARCH_NOTE')
        self.assertEqual(router.parse('trouve ma note projet').intent, 'SEARCH_NOTE')
        self.assertEqual(router.parse('cherche sur internet OpenAI').intent, 'WEB_SEARCH')
    def test_router_preserves_reminder_content_and_trigger(self):
        result=NativeIntentRouter().parse('rappelle-moi demain à 15h de tester AURA_TEST')
        self.assertEqual(result.intent, 'CREATE_REMINDER')
        self.assertEqual(result.slots['raw'], 'tester AURA_TEST')
        self.assertEqual(result.slots['trigger_at'], '2026-10-11T15:00')
        self.assertEqual(NativeIntentRouter().parse('rappelle-moi demain').slots['error'], 'time_required')
    def test_router_transcript_parity(self):
        router=NativeIntentRouter()
        self.assertEqual(router.parse('rappelle-moi dans 20 minutes de vérifier AURA_TEST', source='voice').intent, router.parse('rappelle-moi dans 20 minutes de vérifier AURA_TEST').intent)
    def test_matrix_safety_and_boundaries(self):
        cases = {
            '2026-10-15T14:00': 'OK', '15 octobre à 14h': 'OK', '15 octobre à 14h30': 'OK',
            '15/10 à 14h': 'OK', '15/10/2026 à 14h': 'OK', '15-10-2026 à 14h': 'OK',
            'à 15h': 'OK', 'à 13h': 'OK', 'dans 20 minutes': 'OK',
            'dans 1 heure': 'OK', 'dans 2 heures': 'OK', 'dans 1 jour': 'OK',
            'dans 3 jours': 'OK', 'dans une semaine': 'OK', 'dans 2 semaines': 'OK',
            "aujourd'hui à 15h": 'OK', 'demain à 15h': 'OK', 'après-demain à 15h': 'OK',
            'lundi à 9h': 'OK', 'lundi prochain à 9h': 'OK', 'ce matin': 'INVALID_PAST_TIME',
            'cet après-midi': 'OK', 'ce soir': 'OK', 'demain matin': 'OK',
            'demain après-midi': 'OK', 'demain soir': 'OK', 'demain': 'NEEDS_TIME',
            '31 février à 14h': 'INVALID_DATE', '32 janvier à 14h': 'INVALID_DATE',
            'dans zéro minutes': 'NEEDS_TIME', '2026-01-01T10:00': 'INVALID_PAST_TIME',
            'tous les lundis à 8h': 'UNSUPPORTED_RECURRENCE',
        }
        for phrase, status in cases.items():
            with self.subTest(phrase=phrase): self.assertEqual(parse_french_temporal(phrase, now=NOW).status, status)
        self.assertNotEqual(parse_french_temporal('dimanche à 9h', now=NOW).trigger_at, '2026-10-10T09:00')
    def test_parser_uses_injected_clock(self):
        router=NativeIntentRouter(clock=lambda: NOW)
        self.assertEqual(router.parse('rappelle-moi à 15h de tester').slots['trigger_at'], '2026-10-10T15:00')
    def test_prepared_time_is_not_reinterpreted(self):
        first=parse_french_temporal('dans 20 minutes', now=NOW).trigger_at
        later=parse_french_temporal('dans 20 minutes', now=NOW.replace(hour=15)).trigger_at
        self.assertNotEqual(first, later)
        self.assertEqual(first, '2026-10-10T14:20')
    def test_no_web_fallback_for_invalid_local_reminder(self):
        router=NativeIntentRouter(clock=lambda: NOW)
        invalid=router.parse('rappelle-moi le 31 février à 14h de tester')
        self.assertEqual(invalid.intent, 'CREATE_REMINDER'); self.assertIn('invalid', invalid.slots['error'])
        self.assertNotEqual(invalid.intent, 'WEB_SEARCH')

if __name__ == '__main__': unittest.main()
