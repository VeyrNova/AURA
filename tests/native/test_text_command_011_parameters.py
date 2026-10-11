import unittest
from aura_native.intents.router import NativeIntentRouter

class TextCommand011ParameterTests(unittest.TestCase):
    def setUp(self): self.r=NativeIntentRouter()
    def test_weather_location_and_day(self):
        a=self.r.parse('quel temps fait-il à Marseille'); self.assertEqual(a.intent,'WEATHER_QUERY'); self.assertEqual(a.slots['location'],'Marseille'); self.assertEqual(a.slots['date'],'')
        b=self.r.parse('MÉTÉO à Lyon demain !'); self.assertEqual(b.intent,'WEATHER_QUERY'); self.assertEqual(b.slots['location'],'Lyon'); self.assertEqual(b.slots['date'],'tomorrow')
    def test_parameterized_navigation(self):
        a=self.r.parse('ouvre la météo de Bordeaux'); self.assertEqual(a.intent,'OPEN_MODULE'); self.assertEqual(a.slots,{'module':'weather','location':'Bordeaux'})
        b=self.r.parse('ouvre les documents sur ICPE'); self.assertEqual(b.intent,'OPEN_MODULE'); self.assertEqual(b.slots,{'module':'documents','query':'ICPE'})
        self.assertEqual(self.r.parse('ouvre la météo').slots,{'module':'weather'})
    def test_search_queries_are_preserved(self):
        self.assertEqual(self.r.parse('cherche ICPE sur internet').slots['query'],'ICPE')
        self.assertEqual(self.r.parse('cherche ICPE dans mes notes').slots['query'],'ICPE')
        self.assertEqual(self.r.parse('cherche ICPE dans ma mémoire').slots['query'],'ICPE')
        self.assertIsNone(self.r.parse('explique-moi comment fonctionne une recherche web').intent)
    def test_text_voice_semantic_parity_and_metadata(self):
        a=self.r.parse('ouvre la météo de Marseille',source='keyboard'); b=self.r.parse('ouvre la météo de Marseille',source='voice')
        self.assertEqual(a.intent,b.intent); self.assertEqual(a.slots,b.slots); self.assertNotEqual(a.source,b.source); self.assertTrue(a.request_id and b.request_id)
    def test_parameterized_commands_are_read_only(self):
        self.assertFalse(self.r.parse('ouvre la météo de Marseille').requires_confirmation)
        self.assertFalse(self.r.parse('cherche ICPE sur internet').requires_confirmation)

if __name__=='__main__': unittest.main()
