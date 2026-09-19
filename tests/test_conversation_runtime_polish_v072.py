from __future__ import annotations

import ast
import html
import re
import unittest
from pathlib import Path
from unittest.mock import patch

from voice.voice_profile import VoiceProfile
from voice.xtts_tts import XTTSTTS

from ai.local_first_voice import social_reply
from ai.voice_routing import VoiceRoute, classify_voice_route


ROOT = Path(__file__).resolve().parents[1]


def _load_normalizer():
    source = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "normalize_conversation_text")
    module = ast.Module(body=[fn], type_ignores=[])
    ns = {"html": html, "re": re}
    exec(compile(module, "chat_panel.py", "exec"), ns)
    return ns["normalize_conversation_text"]


class ConversationRuntimePolishV072Tests(unittest.TestCase):
    def test_legacy_br_is_plain_newline(self):
        normalize = _load_normalizer()
        self.assertEqual(normalize("A<br>B<br/>C"), "A\nB\nC")

    def test_normalizer_keeps_emoji_and_unicode(self):
        normalize = _load_normalizer()
        text = "Salut 😊🔥❤️ — déjà prêt"
        self.assertEqual(normalize(text), text)

    def test_social_feeling_question_stays_voice_route(self):
        self.assertIs(classify_voice_route("Comment te sens-tu aujourd'hui ?"), VoiceRoute.VOICE_BRAIN)

    def test_social_feeling_question_has_local_first_reply(self):
        reply = social_reply("Comment te sens-tu aujourd'hui ?")
        self.assertTrue(reply)
        self.assertNotIn("opérationnel", reply.casefold())
        self.assertIn("À ma manière", reply)

    def test_conversation_embeds_visual_result(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("Visual Result embedded in conversation", source)
        self.assertIn("self.chat_panel.add_result_card", source)
        self.assertIn("Conversation duplicate bubble suppressed after embedded result", source)

    def test_knowledge_reference_preempts_router(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        marker = "Deterministic knowledge reference preempts Fast Intelligence Router"
        self.assertIn(marker, source)
        self.assertLess(source.index(marker), source.index("if self.aura_core.should_try_fast_agent_router(text):"))

    def test_tts_worker_has_cancellation_gate(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("self._cancel_event = threading.Event()", source)
        self.assertIn("TTS worker annulé après arbitrage, avant synthèse", source)
        self.assertIn("Fermeture: worker TTS annulé avant shutdown", source)
        self.assertIn("TTS cleanup during shutdown: pending/fallback/prewarm discarded", source)

    def test_xtts_checks_stop_after_model_load(self):
        source = (ROOT / "voice" / "xtts_tts.py").read_text(encoding="utf-8")
        self.assertIn("XTTS native stream annulé pendant le chargement du modèle", source)
        self.assertIn("XTTS native stream annulé pendant le conditionnement", source)
        load_index = source.index("api = self._load_model()", source.index("def _speak_native_stream"))
        cancel_index = source.index("XTTS native stream annulé pendant le chargement du modèle", load_index)
        stream_index = source.index("XTTS native stream start", cancel_index)
        self.assertLess(cancel_index, stream_index)

    def test_xtts_cancel_during_model_load_never_opens_stream(self):
        backend = XTTSTTS(VoiceProfile(xtts_mode="preset", xtts_preset="Ana Florence", xtts_language="fr"))
        backend._device = "cuda"

        def cancelled_load():
            backend._stop_event.set()
            return object()

        with patch.object(backend, "_load_model", side_effect=cancelled_load):
            metrics = backend._speak_native_stream("Réponse en cours")
        self.assertEqual(metrics.chunk_count, 0)
        self.assertTrue(backend._stop_event.is_set())


if __name__ == "__main__":
    unittest.main()
