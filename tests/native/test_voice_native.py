from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from aura_native.intents.dispatcher import NativeActionDispatcher
from aura_native.voice.controller import VoiceController
from aura_native.voice.models import VoiceState
from aura_native.voice.providers import FakeAudioInput, FakeSTT, FakeTTS


import unittest
import numpy as np


class VoiceNativeTests(unittest.TestCase):
  def test_real_contract_nonempty_audio_stop_starts_stt(self):
    class ArrayAudio(FakeAudioInput):
      def stop(self):
        self.stopped += 1
        return np.ones(1600, dtype=np.float32)
    audio, stt = ArrayAudio(), FakeSTT("ouvre météo")
    states = []
    c = VoiceController(audio=audio, stt=stt, on_event=lambda event: states.append(event.state))
    self.assertTrue(c.start().accepted)
    result = c.stop()
    self.assertTrue(result.accepted)
    self.assertEqual(stt.calls, 1)
    self.assertIn(VoiceState.TRANSCRIBING, states)

  def test_empty_numpy_audio_never_calls_stt_and_returns_idle(self):
    class EmptyAudio(FakeAudioInput):
      def stop(self):
        self.stopped += 1
        return np.array([], dtype=np.float32)
    stt=FakeSTT("ne doit pas être appelé")
    c=VoiceController(audio=EmptyAudio(),stt=stt)
    self.assertTrue(c.start().accepted)
    result=c.stop()
    self.assertFalse(result.accepted)
    self.assertEqual(result.error,"no_audio")
    self.assertEqual(stt.calls,0)
    self.assertIs(c.state,VoiceState.IDLE)

  def test_cancel_discards_audio_without_stt(self):
    audio,stt=FakeAudioInput(np.ones(1600,dtype=np.float32)),FakeSTT("ignored")
    c=VoiceController(audio=audio,stt=stt)
    self.assertTrue(c.start().accepted)
    c.cancel()
    self.assertEqual((audio.cancelled,stt.calls),(1,0))
    self.assertIs(c.state,VoiceState.IDLE)

  def test_none_intent_uses_canonical_conversation_fallback(self):
    calls=[]
    c=VoiceController(conversation_fallback=lambda text: calls.append(text) or True)
    result=c.submit_transcript("bonjour")
    self.assertTrue(result.accepted)
    self.assertEqual(calls,["bonjour"])
    self.assertIs(c.state,VoiceState.IDLE)

  def test_deterministic_intent_does_not_use_conversation_fallback(self):
    calls=[]
    c=VoiceController(conversation_fallback=lambda text: calls.append(text) or True)
    result=c.submit_transcript("quel temps fait-il à Marseille")
    self.assertTrue(result.accepted)
    self.assertEqual(calls,[])

  def test_rejected_conversation_fallback_is_recoverable(self):
    c=VoiceController(conversation_fallback=lambda text: False)
    result=c.submit_transcript("bonjour")
    self.assertFalse(result.accepted)
    self.assertEqual(result.error,"conversation_rejected")
    self.assertIs(c.state,VoiceState.IDLE)
  def test_lifecycle_and_transcript_reuses_router(self):
    audio, stt, tts = FakeAudioInput(b"\0"), FakeSTT("ouvre météo"), FakeTTS()
    c = VoiceController(audio=audio, stt=stt, tts=tts)
    self.assertIs(c.state, VoiceState.IDLE)
    self.assertTrue(c.start().accepted and c.state is VoiceState.LISTENING)
    result = c.stop()
    self.assertTrue(result.accepted and result.intent == "OPEN_MODULE")
    self.assertIs(c.state, VoiceState.IDLE)
    self.assertEqual((audio.started, audio.stopped, stt.calls), (1, 1, 1))


  def test_confirmation_safety_for_destructive_intent(self):
    calls = []
    dispatcher = NativeActionDispatcher({"DELETE_NOTE": lambda slots: calls.append(slots)})
    c = VoiceController(stt=FakeSTT("supprime la note 2"), dispatcher=dispatcher)
    c.audio = FakeAudioInput(b"\0")
    c.start(); result = c.stop()
    self.assertTrue(result.requires_confirmation and c.state is VoiceState.THINKING)
    self.assertEqual(calls, [])
    self.assertTrue(c.confirm().accepted)
    self.assertEqual(calls, [{"raw": "2"}])


  def test_fallback_and_device_unavailable_are_explicit(self):
    seen = []
    c = VoiceController(conversation_fallback=lambda text: seen.append(text) or "fallback")
    result = c.submit_transcript("bonjour AURA")
    self.assertTrue(result.accepted and result.message == "fallback" and seen == ["bonjour AURA"])
    unavailable = VoiceController()
    self.assertEqual(unavailable.start().error, "audio_unavailable")


  def test_fake_tts_and_stop_are_offline(self):
    tts = FakeTTS(); c = VoiceController(tts=tts)
    self.assertTrue(c.speak("bonjour").accepted and tts.spoken == ["bonjour"])
    c.stop_speaking(); self.assertEqual(tts.stop_calls, 1)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
