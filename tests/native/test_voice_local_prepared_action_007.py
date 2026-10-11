import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtGui import QGuiApplication

from aura_native.bootstrap.composition import compose_runtime
from aura_native.core.contracts import Command
from aura_native.intents.router import NativeIntentRouter
from aura_native.ui.qt_bridge import NativeCoreBridge
from aura_native.voice.models import VoiceState
from aura_native.voice.qt_bridge import NativeVoiceBridge

ROOT = Path(__file__).resolve().parents[2]
APP = QGuiApplication.instance() or QGuiApplication([])


class VoiceLocalPreparedActionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = compose_runtime(project_root=ROOT, state_dir=Path(self.temp.name))
        self.runtime.start()
        self.core = NativeCoreBridge(self.runtime)
        self.voice = NativeVoiceBridge(parent=APP)
        self.core.voiceLocalActionTerminal.connect(self.voice.onLocalActionTerminal)
        self.addCleanup(self.voice.close)
        self.addCleanup(self.core.close)
        self.addCleanup(self.runtime.stop)
        self.addCleanup(self.temp.cleanup)

    def _voice_prepare(self, text='note que AURA_TEST_007'):
        ident = 'voice-007'
        intent = replace(NativeIntentRouter().parse(text, source='voice'), voice_request_id=ident)
        self.core._dispatch_local_intent(intent)
        aid = self.core.pendingActionId
        self.voice.controller.state = VoiceState.THINKING
        return aid, ident

    def _drain(self):
        self.runtime.bus.drain()

    def test_voice_correlation_is_bound_to_action(self):
        aid, ident = self._voice_prepare()
        self.assertEqual(self.core._voice_action_by_id[aid], ident)
        self.assertEqual(self.runtime.prepared_action_repository.get(aid).state, 'prepared')
        self.assertEqual(self.runtime.local_notes_service.list(), [])

    def test_cancel_releases_voice_and_never_mutates(self):
        aid, _ = self._voice_prepare()
        self.runtime.bus.submit(Command(name='pending_action.cancel', payload={'action_id': aid}))
        self._drain()
        self.assertEqual(self.runtime.prepared_action_repository.get(aid).state, 'cancelled')
        self.assertEqual(self.voice.state, 'idle')
        self.assertEqual(self.runtime.local_notes_service.list(), [])

    def test_confirm_releases_voice_after_one_mutation(self):
        aid, _ = self._voice_prepare()
        self.runtime.bus.submit(Command(name='pending_action.confirm', payload={'action_id': aid}))
        self._drain()
        self.assertEqual(self.runtime.prepared_action_repository.get(aid).state, 'prepared')
        self.runtime._ui_prepared_action_confirmer.confirm(aid)
        self._drain()
        self.assertEqual(self.runtime.prepared_action_repository.get(aid).state, 'executed')
        self.assertEqual(self.voice.state, 'idle')
        self.assertEqual(len(self.runtime.local_notes_service.list()), 1)
        self.runtime.bus.submit(Command(name='pending_action.confirm', payload={'action_id': aid}))
        self._drain()
        self.assertEqual(len(self.runtime.local_notes_service.list()), 1)

    def test_error_releases_voice(self):
        aid, _ = self._voice_prepare()
        self.runtime.local_notes_service.create = lambda *_: (_ for _ in ()).throw(RuntimeError('stale'))
        self.runtime.bus.submit(Command(name='pending_action.confirm', payload={'action_id': aid}))
        self._drain()
        self.assertEqual(self.runtime.prepared_action_repository.get(aid).state, 'prepared')
        self.runtime._ui_prepared_action_confirmer.confirm(aid)
        self._drain()
        self.assertEqual(self.runtime.prepared_action_repository.get(aid).state, 'error')
        self.assertNotEqual(self.voice.state, 'thinking')

    def test_expired_event_releases_voice(self):
        aid, ident = self._voice_prepare()
        self.core._on_pending_state(type('E', (), {'name': 'pending_action.expired', 'payload': {'action_id': aid}})())
        self.assertEqual(self.voice.state, 'idle')
        self.assertIn(ident, self.voice._terminalized_local_requests)

    def test_duplicate_terminal_event_is_idempotent(self):
        aid, ident = self._voice_prepare()
        calls = []
        self.voice._state_from_worker = lambda value: calls.append(value)
        event = type('E', (), {'name': 'pending_action.cancelled', 'payload': {'action_id': aid}})()
        self.core._on_pending_state(event)
        self.core._on_pending_state(event)
        self.assertEqual(calls, ['idle'])
        self.assertIn(ident, self.voice._terminalized_local_requests)

    def test_keyboard_action_does_not_bind_voice(self):
        self.core._dispatch_local_intent(NativeIntentRouter().parse('note que keyboard-007', source='keyboard'))
        aid = self.core.pendingActionId
        self.voice.controller.state = VoiceState.THINKING
        self.runtime.bus.submit(Command(name='pending_action.cancel', payload={'action_id': aid}))
        self._drain()
        self.assertEqual(self.voice.state, 'thinking')

    def test_wrong_action_id_does_not_release_voice(self):
        self._voice_prepare()
        self.core._on_pending_state(type('E', (), {'name': 'pending_action.cancelled', 'payload': {'action_id': 'wrong'}})())
        self.assertEqual(self.voice.state, 'thinking')

    def test_two_voice_actions_are_not_cross_completed(self):
        a, first = self._voice_prepare('note que first-007')
        self.core._voice_action_by_id['second'] = 'voice-second'
        self.voice.controller.state = VoiceState.THINKING
        self.core._on_pending_state(type('E', (), {'name': 'pending_action.cancelled', 'payload': {'action_id': 'second'}})())
        self.assertEqual(self.voice.state, 'idle')
        self.assertNotIn(first, self.voice._terminalized_local_requests)
        self.assertNotIn('second', self.core._voice_action_by_id)
        self.assertNotEqual(a, 'second')

    def test_voice_request_id_differs_from_action_id(self):
        aid, ident = self._voice_prepare()
        self.assertNotEqual(aid, ident)

    def test_cancel_does_not_submit_gemini(self):
        aid, _ = self._voice_prepare()
        before = self.core._conversation_status
        self.runtime.bus.submit(Command(name='pending_action.cancel', payload={'action_id': aid}))
        self._drain()
        self.assertEqual(self.core._conversation_status, before)

    def test_voice_signal_path_carries_two_values(self):
        seen = []
        self.voice.localTranscriptReady.connect(lambda text, ident: seen.append((text, ident)))
        self.voice._on_transcript('note que signal-007')
        self.assertEqual(seen[0][0], 'note que signal-007')
        self.assertTrue(seen[0][1])


if __name__ == '__main__':
    unittest.main()
