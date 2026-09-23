from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'ui' / 'main_window.py').read_text(encoding='utf-8')


class Patch267ComposerIconSourceTests(unittest.TestCase):
    def test_semantic_glyphs_are_defined(self):
        self.assertIn('COMPOSER_ACTION_GLYPHS', SOURCE)
        self.assertIn('"attach": "📎"', SOURCE)
        self.assertIn('"send": "➤"', SOURCE)
        self.assertIn('"microphone": "🎤"', SOURCE)

    def test_role_inference_covers_expected_hints(self):
        for token in (
            'composerplus', 'pièce jointe', 'envoyer', 'micbutton', 'microphone'
        ):
            with self.subTest(token=token):
                self.assertIn(token, SOURCE)

    def test_main_window_refreshes_icons_with_timer(self):
        self.assertIn('self._composer_icon_timer = QTimer(self)', SOURCE)
        self.assertIn('self._composer_icon_timer.timeout.connect(self._apply_composer_action_icons)', SOURCE)
        self.assertIn('QTimer.singleShot(0, self._apply_composer_action_icons)', SOURCE)
        self.assertIn('QTimer.singleShot(1200, self._apply_composer_action_icons)', SOURCE)

    def test_runtime_scan_uses_qabstractbutton(self):
        self.assertIn('self.findChildren(QAbstractButton)', SOURCE)
        self.assertIn('button.setProperty("auraSemanticActionIcon", role)', SOURCE)


if __name__ == '__main__':
    unittest.main()
