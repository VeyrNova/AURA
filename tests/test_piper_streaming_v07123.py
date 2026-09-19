from regression_compat import assert_version_at_least
import sys
import time
import types
import unittest
from unittest.mock import patch

from config.settings import settings
from voice.text_to_speech import PiperPreparedSegment, PiperTTS
from voice.voice_engine import RealtimePiperVoiceSession, VoiceEngine


class FakeChunk:
    sample_rate = 22050
    sample_width = 2
    sample_channels = 1

    def __init__(self, payload=b"\x00\x00" * 64):
        self.audio_int16_bytes = payload


class FakeVoice:
    def __init__(self, chunks=3, delay=0.002):
        self.chunks = chunks
        self.delay = delay
        self.calls = 0

    def synthesize(self, text, syn_config=None):
        self.calls += 1
        for _ in range(self.chunks):
            time.sleep(self.delay)
            yield FakeChunk()


class FakeStream:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.started = False
        self.stopped = False
        self.aborted = False
        self.closed = False
        self.writes = []

    def start(self): self.started = True
    def write(self, payload): self.writes.append(bytes(payload))
    def stop(self): self.stopped = True
    def abort(self): self.aborted = True
    def close(self): self.closed = True


class PiperStreamingV07123Tests(unittest.TestCase):
    def test_version_and_streaming_defaults(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.1.2.3")
        self.assertTrue(settings.PIPER_STREAMING_ENABLED)
        self.assertTrue(settings.PIPER_BACKGROUND_PREWARM)

    def test_native_piper_chunks_reach_one_persistent_output_stream(self):
        backend = PiperTTS()
        fake_voice = FakeVoice(chunks=3)
        made = []

        def factory(**kwargs):
            stream = FakeStream(**kwargs)
            made.append(stream)
            return stream

        fake_sd = types.SimpleNamespace(RawOutputStream=factory)
        with patch.object(backend, "_load_voice", return_value=fake_voice), \
             patch.object(backend, "_synthesis_config", return_value=None), \
             patch.dict(sys.modules, {"sounddevice": fake_sd}):
            metrics = backend._stream_text("Bonjour AURA", {}, close_stream=True)

        self.assertTrue(metrics.streaming)
        self.assertEqual(metrics.chunk_count, 3)
        self.assertGreater(metrics.time_to_audio_seconds, 0.0)
        self.assertEqual(len(made), 1)
        self.assertEqual(len(made[0].writes), 3)
        self.assertTrue(made[0].started)
        self.assertTrue(made[0].stopped)
        self.assertTrue(made[0].closed)

    def test_realtime_piper_session_is_lazy_and_keeps_stream_between_segments(self):
        backend = PiperTTS()
        fake_voice = FakeVoice(chunks=1)
        made = []
        fake_sd = types.SimpleNamespace(RawOutputStream=lambda **kw: made.append(FakeStream(**kw)) or made[-1])

        with patch.object(backend, "_load_voice", return_value=fake_voice), \
             patch.object(backend, "_synthesis_config", return_value=None), \
             patch.dict(sys.modules, {"sounddevice": fake_sd}):
            session = RealtimePiperVoiceSession(backend, fallback_active=True)
            first = session.synthesize("Première phrase.", index=0)
            self.assertIsInstance(first, PiperPreparedSegment)
            self.assertEqual(fake_voice.calls, 0, "prepare must not synthesize the whole sentence")
            session.play(first)
            second = session.synthesize("Deuxième phrase.", index=1)
            session.play(second)
            self.assertEqual(fake_voice.calls, 2)
            self.assertEqual(len(made), 1, "one PortAudio stream must survive the turn")
            self.assertGreater(first.first_audio_at, 0.0)
            session.close()
            self.assertTrue(made[0].stopped)
            self.assertTrue(made[0].closed)

    def test_voice_engine_opens_realtime_piper_when_xtts_is_forced_to_fallback(self):
        engine = VoiceEngine.__new__(VoiceEngine)
        piper = PiperTTS()
        engine.tts = object()
        engine.fallback_tts = piper
        engine._last_fallback_active = False
        engine._last_engine_used = ""
        engine._last_tts_error = "old"
        with patch.object(engine, "_tts_available", side_effect=lambda obj: obj is piper), \
             patch.object(piper, "begin_realtime_pipeline", return_value=0.0):
            session = engine.open_realtime_voice_session(force_fallback=True)
        self.assertIsInstance(session, RealtimePiperVoiceSession)
        self.assertEqual(engine._last_engine_used, "piper")
        self.assertTrue(engine._last_fallback_active)

    def test_stop_aborts_active_stream(self):
        backend = PiperTTS()
        stream = FakeStream()
        backend._active_stream = stream
        backend.stop()
        self.assertTrue(backend._stop_event.is_set())
        self.assertTrue(stream.aborted)
        self.assertTrue(stream.closed)


if __name__ == "__main__":
    unittest.main()
