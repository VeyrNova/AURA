from __future__ import annotations
import sys, unittest, threading, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/'src'))
from PySide6.QtCore import QCoreApplication
from aura_native.voice.qt_bridge import NativeVoiceBridge
from aura_native.voice.controller import VoiceController
from aura_native.voice.providers import FakeAudioInput, FakeSTT, FakeTTS

class VoiceQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QCoreApplication.instance() or QCoreApplication([])
    def test_bridge_is_lazy_and_exposes_state(self):
        b=NativeVoiceBridge(VoiceController(audio=FakeAudioInput(),stt=FakeSTT('ouvre mail'),tts=FakeTTS()))
        self.assertEqual(b.state,'idle'); self.assertFalse(b._thread.isRunning()); self.assertTrue(b.available)
        b.close()

    def test_bridge_accepts_injected_canonical_conversation_fallback(self):
        seen=[]
        b=NativeVoiceBridge(VoiceController(audio=FakeAudioInput(b"x"),stt=FakeSTT("bonjour"),tts=FakeTTS(),
                                             conversation_fallback=lambda text: seen.append(text) or True))
        result=b.controller.submit_transcript("bonjour")
        self.assertTrue(result.accepted)
        self.assertEqual(seen,["bonjour"])
        b.close()

    def test_bridge_queues_conversation_request_signal(self):
        seen=[]
        b=NativeVoiceBridge(VoiceController(audio=FakeAudioInput(b"x"),stt=FakeSTT("bonjour"),tts=FakeTTS()))
        b.conversationRequested.connect(seen.append)
        result=b.controller.submit_transcript("bonjour")
        self.assertTrue(result.accepted)
        self.assertEqual(seen,["bonjour"])
        b.close()
    def test_qml_contract_uses_voice_bridge(self):
        source=(ROOT/'app/qml/components/Composer.qml').read_text(encoding='utf-8')
        self.assertIn('voiceBridge.startListening()',source); self.assertIn('voiceBridge.stopListening()',source)
        self.assertIn('voiceBridge.cancel()',source)
        self.assertIn('MouseArea {',source)
        self.assertIn('onPressed:',source)
        self.assertIn('onReleased:',source)
        self.assertIn('onCanceled:',source)
        self.assertIn('preventStealing: true',source)
        self.assertIn('voiceBridge.state === "idle"',source)
        self.assertIn('voiceBridge.state === "listening"',source)
        self.assertIn('voiceBridge.statusText',source)

    def _pump_until(self, predicate, timeout=2.0):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline and not predicate():
            self.app.processEvents(); time.sleep(.005)
        self.app.processEvents()
        self.assertTrue(predicate())

    def test_duplicate_press_and_release_during_start_are_serialized(self):
        class BlockingAudio(FakeAudioInput):
            def __init__(self):
                super().__init__(); self.entered=threading.Event(); self.release=threading.Event()
            def start(self):
                self.started += 1; self.entered.set(); self.release.wait(1.0)
        audio=BlockingAudio()
        b=NativeVoiceBridge(VoiceController(audio=audio,stt=FakeSTT(''),tts=FakeTTS()))
        self.assertTrue(b.startListening())
        self.assertTrue(audio.entered.wait(1.0))
        self.assertFalse(b.startListening())
        self.assertTrue(b.stopListening())
        self.assertTrue(b._stop_pending)
        audio.release.set()
        self._pump_until(lambda: audio.stopped == 1)
        self.assertEqual((audio.started,audio.stopped),(1,1))
        b.close()

    def test_cancel_during_start_cannot_leave_audio_open(self):
        class BlockingAudio(FakeAudioInput):
            def __init__(self):
                super().__init__(); self.entered=threading.Event(); self.release=threading.Event()
            def start(self):
                self.started += 1; self.entered.set(); self.release.wait(1.0)
        audio=BlockingAudio()
        b=NativeVoiceBridge(VoiceController(audio=audio,stt=FakeSTT(''),tts=FakeTTS()))
        self.assertTrue(b.startListening()); self.assertTrue(audio.entered.wait(1.0))
        b.cancel(); audio.release.set()
        self._pump_until(lambda: audio.cancelled == 1)
        self.assertEqual(audio.started,1)
        b.close()

    def test_stuck_transcribing_terminal_state_is_forwarded(self):
        audio=FakeAudioInput(b"x")
        controller=VoiceController(audio=audio, stt=FakeSTT("bonjour"), tts=FakeTTS(),
                                    conversation_fallback=lambda text: True)
        b=NativeVoiceBridge(controller)
        states=[]
        b.stateChanged.connect(lambda: states.append(b.state))
        self.assertTrue(b.startListening())
        self._pump_until(lambda: audio.started == 1)
        self.assertTrue(b.stopListening())
        self._pump_until(lambda: audio.stopped == 1 and b.state == "idle")
        self.assertGreaterEqual(len(states), 2)
        self.assertEqual(states[-1], "idle")
        self.assertNotEqual(b.state, "transcribing")
        b.close()

if __name__=='__main__': unittest.main(verbosity=2)
