from regression_compat import assert_version_at_least
import sys
import time
import types
import unittest
from unittest.mock import patch

from config.settings import settings
from voice.text_to_speech import PiperTTS, split_piper_progressive_segments


class FakeChunk:
    sample_rate = 22050
    sample_width = 2
    sample_channels = 1
    audio_int16_bytes = b"\x00\x00" * 32


class TextSensitiveVoice:
    def __init__(self):
        self.calls = []

    def synthesize(self, text, syn_config=None):
        self.calls.append(text)
        # Simulate the observed Piper behavior: longer requests take longer
        # before yielding first PCM. Progressive splitting must keep calls small.
        time.sleep(min(0.001 + len(text) * 0.00001, 0.004))
        yield FakeChunk()


class FakeStream:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.writes = []
        self.started = self.stopped = self.closed = self.aborted = False
    def start(self): self.started = True
    def write(self, payload): self.writes.append(bytes(payload))
    def stop(self): self.stopped = True
    def abort(self): self.aborted = True
    def close(self): self.closed = True


class PiperProgressiveV07124Tests(unittest.TestCase):
    def test_version_and_progressive_defaults(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.1.2.4")
        self.assertGreaterEqual(settings.PIPER_FIRST_SEGMENT_CHARS, 32)
        self.assertGreaterEqual(settings.PIPER_NEXT_SEGMENT_CHARS, settings.PIPER_FIRST_SEGMENT_CHARS)

    def test_splitter_bounds_first_segment_and_preserves_text(self):
        text = (
            "À Vidauban, le ciel reste dégagé avec vingt-six degrés Celsius, "
            "puis quelques nuages arriveront en soirée. Le vent restera faible "
            "et aucune pluie significative n'est attendue aujourd'hui."
        )
        parts = split_piper_progressive_segments(text, first_limit=64, next_limit=100)
        self.assertGreaterEqual(len(parts), 2)
        self.assertLessEqual(len(parts[0]), 64)
        self.assertTrue(all(len(p) <= 100 for p in parts[1:]))
        self.assertEqual(" ".join(parts), " ".join(text.split()))

    def test_long_direct_speech_uses_multiple_piper_calls_one_audio_stream(self):
        backend = PiperTTS()
        voice = TextSensitiveVoice()
        streams = []
        fake_sd = types.SimpleNamespace(RawOutputStream=lambda **kw: streams.append(FakeStream(**kw)) or streams[-1])
        text = " ".join(["Voici une réponse météo détaillée pour tester la parole progressive."] * 6)
        with patch.object(backend, "_load_voice", return_value=voice), \
             patch.object(backend, "_synthesis_config", return_value=None), \
             patch.dict(sys.modules, {"sounddevice": fake_sd}):
            metrics = backend._stream_progressive_text(text, {}, close_stream=True)
        self.assertGreater(len(voice.calls), 1)
        self.assertLessEqual(len(voice.calls[0]), settings.PIPER_FIRST_SEGMENT_CHARS)
        self.assertEqual(len(streams), 1)
        self.assertEqual(len(streams[0].writes), len(voice.calls))
        self.assertGreater(metrics.time_to_audio_seconds, 0.0)
        self.assertEqual(metrics.chunk_count, len(voice.calls))

    def test_stop_between_segments_prevents_further_synthesis(self):
        backend = PiperTTS()
        voice = TextSensitiveVoice()
        stream = FakeStream()
        fake_sd = types.SimpleNamespace(RawOutputStream=lambda **kw: stream)
        calls = {"n": 0}
        def first_audio(_ts):
            calls["n"] += 1
            backend._stop_event.set()
        text = "Une première partie assez courte. Une seconde partie ne doit pas être synthétisée après annulation."
        with patch.object(backend, "_load_voice", return_value=voice), \
             patch.object(backend, "_synthesis_config", return_value=None), \
             patch.dict(sys.modules, {"sounddevice": fake_sd}):
            backend._stop_event.clear()
            metrics = backend._stream_progressive_text(text, {}, close_stream=True, on_first_audio=first_audio)
        self.assertEqual(calls["n"], 1)
        self.assertEqual(len(voice.calls), 1)
        self.assertEqual(metrics.chunk_count, 1)
        self.assertTrue(stream.aborted)


if __name__ == "__main__":
    unittest.main()
