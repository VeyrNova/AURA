import unittest
from aura_native.intents.router import NativeIntentRouter


class TextCommand013MusicDocumentsTests(unittest.TestCase):
    def setUp(self):
        self.router = NativeIntentRouter()

    def test_music_controls_preserve_parameters(self):
        cases = {
            'ouvre musique': ('MUSIC_OPEN', {'module':'music'}),
            'joue la musique C:/tmp/AURA.wav': ('MUSIC_PLAY', {'query':'C:/tmp/AURA.wav'}),
            'mets la musique en pause': ('MUSIC_PAUSE', {}),
            'reprends la musique': ('MUSIC_RESUME', {}),
            'règle le volume 42': ('MUSIC_VOLUME', {'volume':42}),
            'avance la musique à 50 pourcent': ('MUSIC_SEEK', {'position':50}),
        }
        for text, (intent, slots) in cases.items():
            with self.subTest(text=text):
                result = self.router.parse(text)
                self.assertEqual(result.intent, intent)
                self.assertEqual(result.slots, slots)

    def test_music_voice_uses_same_router(self):
        text = 'mets la musique en pause'
        self.assertEqual(self.router.parse(text, source='keyboard').intent, self.router.parse(text, source='voice').intent)

    def test_documents_read_commands_preserve_identity(self):
        result = self.router.parse('cherche un document AURA_ALPHA')
        self.assertEqual((result.intent, result.slots['query']), ('DOCUMENTS_SEARCH', 'AURA_ALPHA'))
        result = self.router.parse('ouvre le document AURA_ALPHA.txt', source='voice')
        self.assertEqual((result.intent, result.slots['document_id']), ('DOCUMENTS_OPEN', 'AURA_ALPHA.txt'))

    def test_no_prepared_action_or_llm_for_read_only_commands(self):
        for text in ('ouvre musique', 'cherche un document AURA_ALPHA'):
            result = self.router.parse(text)
            self.assertTrue(result.deterministic)
            self.assertFalse(result.requires_confirmation)


if __name__ == '__main__':
    unittest.main()
