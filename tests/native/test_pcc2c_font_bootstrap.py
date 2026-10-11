import unittest
from pathlib import Path
ROOT=Path(__file__).parents[2]
class Pcc2cFontBootstrapTests(unittest.TestCase):
    def test_native_bootstrap_uses_system_font_dir_without_bundled_fonts(self):
        source=(ROOT/'app/main.py').read_text(encoding='utf-8')
        self.assertIn('QT_QPA_FONTDIR', source)
        self.assertIn('Fonts', source)
        self.assertNotIn('QT_QPA_FONTDIR="PySide6/lib/fonts"', source)
    def test_pcc_launcher_delegates_to_official_main(self):
        source=(ROOT/'tests/native/_evidence/provider_credentials_center_ui.py').read_text(encoding='utf-8')
        self.assertIn("app/main.py", source)
        self.assertNotIn('.ttf', source.lower())
