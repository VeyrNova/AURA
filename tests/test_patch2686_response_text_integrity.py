from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location('aura_text_rendering', ROOT/'ui'/'text_rendering.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class Patch2686Tests(unittest.TestCase):
    def test_repairs_latin1_mojibake(self):
        self.assertEqual(mod.normalize_unicode_text('RÃ©sumÃ© â\x80\x93 clÃ©'), 'Résumé – clé')

    def test_preserves_legitimate_french(self):
        self.assertEqual(mod.normalize_unicode_text('Âge : déjà prêt'), 'Âge : déjà prêt')

    def test_removes_bidi_and_zero_width_controls(self):
        self.assertEqual(mod.normalize_unicode_text('Bon\u200bjour \u202eAURA\u202c'), 'Bonjour AURA')

    def test_streams_force_utf8_bytes(self):
        src=(ROOT/'ai'/'llm_manager.py').read_text(encoding='utf-8')
        self.assertIn('def _decode_utf8_stream_line', src)
        self.assertGreaterEqual(src.count('iter_lines(decode_unicode=False)'), 3)
        self.assertNotIn('iter_lines(decode_unicode=True):', src)

    def test_results_panel_renders_markdown(self):
        src=(ROOT/'ui'/'holographic_results_panel.py').read_text(encoding='utf-8')
        self.assertIn('self.body.setMarkdown(clean_text)', src)
        self.assertIn('normalize_markdown_text', src)

    def test_conversation_result_card_strips_raw_markdown_markup(self):
        src=(ROOT/'ui'/'chat_panel.py').read_text(encoding='utf-8')
        self.assertIn('markdown_doc.setMarkdown(markdown_text)', src)
        self.assertIn('markdown_doc.toPlainText()', src)

if __name__ == '__main__':
    unittest.main()
