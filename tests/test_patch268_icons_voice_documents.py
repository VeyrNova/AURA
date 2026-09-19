from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
import tempfile
import unittest

from services.document_analysis import extract_document, inject_document_context, select_document_context


class Patch268DocumentTests(unittest.TestCase):
    def test_plain_text_document_is_extracted_and_injected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rapport.txt"
            path.write_text("Station A: pression 4.2 bar.\nMaintenance prévue vendredi.", encoding="utf-8")
            doc = extract_document(str(path))
            self.assertIn("4.2 bar", doc.text)
            messages = [{"role": "system", "content": "base"}, {"role": "user", "content": "Quelle pression ?"}]
            enriched = inject_document_context(messages, doc, query="pression")
            self.assertEqual(enriched[-1]["role"], "user")
            self.assertIn("DÉBUT DU DOCUMENT", enriched[-2]["content"])
            self.assertIn("4.2 bar", enriched[-2]["content"])

    def test_long_document_context_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "long.txt"
            path.write_text(("alpha pression cible 4.2 bar\n" * 4000), encoding="utf-8")
            doc = extract_document(str(path))
            selected = select_document_context(doc, query="pression cible", max_chars=9000)
            self.assertLessEqual(len(selected.text), 9000)
            self.assertIn("pression cible", selected.text)


class Patch268SourceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.main = (cls.root / "ui" / "main_window.py").read_text(encoding="utf-8")
        cls.chat = (cls.root / "ui" / "chat_panel.py").read_text(encoding="utf-8")
        cls.home = (cls.root / "ui" / "final_modules.py").read_text(encoding="utf-8")
        cls.icons = (cls.root / "ui" / "action_icons.py").read_text(encoding="utf-8")

    def test_no_emoji_action_glyph_contract(self):
        self.assertNotIn('COMPOSER_ACTION_GLYPHS', self.main)
        self.assertIn('QPainter vectors instead of emoji/font glyphs', self.icons)
        self.assertIn('apply_action_icon(self.attach_button, "attach"', self.chat)
        self.assertIn('apply_action_icon(self.mic_button, "microphone"', self.chat)
        self.assertIn('apply_action_icon(self.send_button, "send"', self.chat)

    def test_attachment_button_is_functional(self):
        self.assertIn('attachment_requested = Signal()', self.chat)
        self.assertIn('self.attach_button.clicked.connect(self.attachment_requested.emit)', self.chat)
        self.assertIn('self.chat_panel.attachment_requested.connect(self._on_attachment_requested)', self.main)
        self.assertIn('QFileDialog.getOpenFileName', self.main)
        self.assertIn('extract_document(self.path)', self.main)
        self.assertIn('inject_document_context(messages, document_context, query=text)', self.main)

    def test_home_mic_and_attachment_are_wired(self):
        self.assertIn('attachment_requested = Signal()', self.home)
        self.assertIn('self.home_composer.microphone_pressed.connect(self._on_microphone_pressed)', self.main)
        self.assertIn('self.home_composer.set_microphone_available(status.input_ready)', self.main)

    def test_voice_guardian_has_functional_local_retry(self):
        self.assertIn('Voice-safe local fallback: releasing XTTS temporarily', self.main)
        self.assertIn('retry_profile["preserve_xtts_for_voice"] = False', self.main)
        self.assertIn('self.aura_core.voice_engine.release_xtts_model()', self.main)

    def test_hud_exposes_groq_state(self):
        self.assertIn('NEURAL LINK · GROQ', self.main)
        self.assertIn('GROQ: CLÉ NON CHARGÉE', self.main)


if __name__ == "__main__":
    unittest.main()
