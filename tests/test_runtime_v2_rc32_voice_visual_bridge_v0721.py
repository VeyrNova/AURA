from __future__ import annotations

import struct
import unittest
from pathlib import Path

from core.version import AURA_BUILD, AURA_RELEASE_CHANNEL, AURA_VERSION
from voice.voice_engine import VoiceEngine
from voice.xtts_tts import _float32_pcm_peak

ROOT = Path(__file__).resolve().parents[1]


class _FakeAmplitudeBackend:
    def __init__(self):
        self.bound = []

    def set_visual_amplitude_callback(self, callback):
        self.bound.append(callback)


class RuntimeV2RC32VoiceVisualBridgeTests(unittest.TestCase):
    def test_release_identity(self):
        self.assertEqual(AURA_VERSION, "0.7.2.1")
        self.assertEqual(AURA_BUILD, "2026.08.15.9")
        self.assertEqual(AURA_RELEASE_CHANNEL, "consolidation-rc3.2")

    def test_voice_engine_exposes_visual_amplitude_facade(self):
        primary = _FakeAmplitudeBackend()
        fallback = _FakeAmplitudeBackend()
        engine = object.__new__(VoiceEngine)
        engine._visual_amplitude_callback = None
        engine.tts = primary
        engine.cloud_fallback_tts = None
        engine.fallback_tts = fallback

        received = []
        callback = lambda value: received.append(value)
        self.assertTrue(engine.set_visual_amplitude_callback(callback))

        self.assertIs(engine._visual_amplitude_callback, callback)
        self.assertEqual(primary.bound, [callback])
        self.assertEqual(fallback.bound, [callback])

        self.assertTrue(engine.set_visual_amplitude_callback(None))
        self.assertIsNone(engine._visual_amplitude_callback)
        self.assertIsNone(primary.bound[-1])
        self.assertIsNone(fallback.bound[-1])

    def test_float32_pcm_peak_is_bounded_and_tracks_audio(self):
        payload = b"".join(struct.pack("f", value) for value in (0.0, -0.2, 0.75, -1.2, 0.3))
        self.assertAlmostEqual(_float32_pcm_peak(payload), 1.0, places=4)
        quiet = b"".join(struct.pack("f", value) for value in (0.0, 0.05, -0.1))
        self.assertAlmostEqual(_float32_pcm_peak(quiet), 0.1, places=4)
        self.assertEqual(_float32_pcm_peak(b""), 0.0)

    def test_ui_binds_optional_bridge_without_exception_traceback_contract(self):
        src = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8", errors="replace")
        start = src.index("amplitude_binder = getattr")
        block = src[start:start + 900]
        self.assertIn('"set_visual_amplitude_callback"', block)
        self.assertIn("Live voice amplitude bridge bound: real PCM waveform enabled", block)
        self.assertIn("Live voice amplitude bridge unavailable; state-reactive waveform kept", block)
        self.assertNotIn("exc_info=True", block)

    def test_xtts_persistent_bridge_receives_real_pcm_callback(self):
        src = (ROOT / "voice" / "xtts_tts.py").read_text(encoding="utf-8", errors="replace")
        self.assertIn("amplitude_callback=self._visual_amplitude_callback", src)
        self.assertIn("self._emit_amplitude(payload)", src)
        self.assertIn("self._emit_visual_amplitude(item)", src)
        self.assertIn("callback(_float32_pcm_peak(payload))", src)


if __name__ == "__main__":
    unittest.main()
