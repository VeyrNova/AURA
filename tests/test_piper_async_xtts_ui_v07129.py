from regression_compat import assert_version_at_least
import sys
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from config.settings import settings
from voice.text_to_speech import PiperTTS


class FakeChunk:
    sample_rate = 22050
    sample_width = 2
    sample_channels = 1
    audio_int16_bytes = b"\x00\x00" * 64


class TimedVoice:
    def __init__(self):
        self.calls = []

    def synthesize(self, text, syn_config=None):
        self.calls.append((text, time.perf_counter()))
        time.sleep(0.003)
        yield FakeChunk()


class SlowPlaybackStream:
    def __init__(self, **kwargs):
        self.started = False
        self.closed = False
        self.aborted = False
        self.first_write_started = 0.0
        self.first_write_finished = 0.0
        self.writes = 0

    def start(self):
        self.started = True

    def write(self, payload):
        self.writes += 1
        if self.writes == 1:
            self.first_write_started = time.perf_counter()
            time.sleep(0.050)
            self.first_write_finished = time.perf_counter()
        else:
            time.sleep(0.002)

    def stop(self):
        pass

    def abort(self):
        self.aborted = True

    def close(self):
        self.closed = True


class PiperAsyncXtTSUiV07129Tests(unittest.TestCase):
    def test_version_and_bounded_queue_default(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.1.2.9")
        self.assertGreaterEqual(settings.PIPER_AUDIO_QUEUE_CHUNKS, 1)
        self.assertLessEqual(settings.PIPER_AUDIO_QUEUE_CHUNKS, 12)

    def test_next_segment_synthesizes_while_previous_audio_is_being_written(self):
        backend = PiperTTS()
        voice = TimedVoice()
        stream = SlowPlaybackStream()
        fake_sd = types.SimpleNamespace(RawOutputStream=lambda **kw: stream)
        text = (
            "À Tokyo, 28 degrés. "
            "Le ciel est couvert avec quelques averses possibles plus tard aujourd'hui. "
            "Le vent reste faible."
        )
        with patch.object(backend, "_load_voice", return_value=voice), \
             patch.object(backend, "_synthesis_config", return_value=None), \
             patch.dict(sys.modules, {"sounddevice": fake_sd}):
            metrics = backend._stream_progressive_text(text, {}, close_stream=True)

        self.assertGreaterEqual(len(voice.calls), 2)
        second_synth_started = voice.calls[1][1]
        self.assertGreater(stream.first_write_finished, stream.first_write_started)
        self.assertGreaterEqual(second_synth_started, stream.first_write_started)
        self.assertLess(second_synth_started, stream.first_write_finished)
        self.assertGreaterEqual(metrics.chunk_count, 2)

    def test_voice_settings_handles_guardian_block_without_exception_logging_path(self):
        source = Path("ui/main_window.py").read_text(encoding="utf-8")
        settings_block = source[source.index("    def _open_voice_settings") : source.index("    def _open_voice_lab")]
        self.assertIn("except ResourcePressureError as exc:", settings_block)
        self.assertIn("XTTS haute qualité est indisponible", settings_block)
        self.assertLess(settings_block.index("except ResourcePressureError as exc:"), settings_block.index("except Exception:"))

        lab_start = source.index("    def _open_voice_lab")
        lab_end = source.index("    def _on_voice_profile_saved", lab_start)
        lab_block = source[lab_start:lab_end]
        self.assertIn("except ResourcePressureError as exc:", lab_block)
        self.assertIn("Voice Lab XTTS indisponible", lab_block)


if __name__ == "__main__":
    unittest.main()
