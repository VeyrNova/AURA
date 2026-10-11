import unittest, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/'src'))
from aura_native.intents.router import NativeIntentRouter
from aura_native.intents.dispatcher import NativeActionDispatcher

class TextCommandsTests(unittest.TestCase):
 def setUp(self): self.r=NativeIntentRouter()
 def test_open_weather_search_contacts_documents(self):
  self.assertEqual(self.r.parse('Ouvre Mail').slots['module'],'mail')
  self.assertEqual(self.r.parse('quel temps fait-il à Marseille ?').slots['location'],'Marseille')
  self.assertEqual(self.r.parse('cherche Qt 6 documentation').slots['query'],'Qt 6 documentation')
  self.assertEqual(self.r.parse('cherche Alice dans mes contacts').intent,'CONTACT_SEARCH')
  self.assertEqual(self.r.parse('liste mes documents').intent,'DOCUMENTS_LIST')
 def test_fallback_and_false_positives(self):
  self.assertFalse(self.r.parse('bonjour AURA').recognized)
  self.assertFalse(self.r.parse('je parle de la météo dans mon projet').recognized)
  self.assertFalse(self.r.parse('mon document explique les contacts électriques').recognized)
 def test_confirmation_and_dispatch(self):
  x=self.r.parse('supprime la note 3'); self.assertTrue(x.requires_confirmation); self.assertEqual(x.slots['raw'],'3')
  self.assertEqual(NativeActionDispatcher().dispatch(self.r.parse('ouvre mail')).route,'module')
 def test_normalization_is_pure(self):
  self.assertEqual(self.r.parse('  OUVRE   LES   MAILS. ').intent,'OPEN_MODULE')
if __name__=='__main__': unittest.main()
