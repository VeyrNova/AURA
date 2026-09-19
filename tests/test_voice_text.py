import unittest

from voice.text_to_speech import sanitize_for_speech


class VoiceSpeechTextTests(unittest.TestCase):
    def test_markdown_is_simplified_for_speech(self):
        text = "**Bonjour** `AURA` [documentation](https://example.com)"
        spoken = sanitize_for_speech(text, max_chars=500)
        self.assertIn("Bonjour", spoken)
        self.assertIn("AURA", spoken)
        self.assertNotIn("**", spoken)
        self.assertNotIn("https://", spoken)

    def test_code_block_is_not_read_aloud(self):
        text = "Voici le code:\n```python\nprint('secret')\n```\nTermine."
        spoken = sanitize_for_speech(text, max_chars=500)
        self.assertNotIn("print", spoken)
        self.assertIn("code est affiché", spoken)

    def test_long_text_is_bounded(self):
        text = ("Phrase courte. " * 200).strip()
        spoken = sanitize_for_speech(text, max_chars=220)
        self.assertLess(len(spoken), 320)
        self.assertIn("suite est affichée", spoken)


if __name__ == "__main__":
    unittest.main()
