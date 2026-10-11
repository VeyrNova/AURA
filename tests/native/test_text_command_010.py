import unittest
from aura_native.intents.router import NativeIntentRouter

class TextCommand010Tests(unittest.TestCase):
    def setUp(self): self.r=NativeIntentRouter()
    def test_aliases_and_parameters(self):
        self.assertEqual(self.r.parse('Aura, note que Test').intent,'CREATE_NOTE')
        self.assertEqual(self.r.parse('prends une note Test').intent,'CREATE_NOTE')
        self.assertEqual(self.r.parse('je dois tester').intent,'CREATE_TASK')
        self.assertEqual(self.r.parse('marque la tâche Test comme terminée').intent,'COMPLETE_TASK')
        self.assertEqual(self.r.parse('montre-moi mes notes').intent,'LIST_NOTES')
        self.assertEqual(self.r.parse('ouvre mes tâches').slots.get('module'),'tasks')
    def test_search_and_pc_disambiguation(self):
        self.assertEqual(self.r.parse('cherche dans mes notes projet').intent,'SEARCH_NOTE')
        self.assertEqual(self.r.parse('cherche les fenêtres PVC sur internet').intent,'WEB_SEARCH')
        self.assertIsNone(self.r.parse('explique-moi ce qu’est un processus Windows').intent)
    def test_mutation_never_falls_to_llm(self):
        intent=self.r.parse('supprime la note')
        self.assertEqual(intent.intent,'DELETE_NOTE'); self.assertTrue(intent.slots.get('error'))
    def test_voice_and_text_share_intent(self):
        self.assertEqual(self.r.parse('liste les fenêtres ouvertes',source='keyboard').intent,
                         self.r.parse('liste les fenêtres ouvertes',source='voice').intent)

if __name__=='__main__': unittest.main()
