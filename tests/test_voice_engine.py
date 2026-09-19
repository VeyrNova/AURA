import unittest
from contextlib import ExitStack
from unittest.mock import patch

from voice.voice_engine import VoiceEngine


class VoiceEngineTests(unittest.TestCase):
    @staticmethod
    def _disable_tts_backend(stack: ExitStack, backend) -> None:
        """Make one TTS backend deterministically unavailable for isolation tests."""
        if backend is None:
            return
        stack.enter_context(patch.object(backend, "dependency_available", return_value=False))
        stack.enter_context(patch.object(backend, "model_ready", return_value=False))
        stack.enter_context(patch.object(backend, "is_available", return_value=False))

    def test_status_is_fail_safe_without_dependencies_or_models(self):
        engine = VoiceEngine()
        with ExitStack() as stack:
            stack.enter_context(patch.object(engine.recorder, "dependencies_available", return_value=False))
            stack.enter_context(patch.object(engine.stt, "dependency_available", return_value=False))
            stack.enter_context(patch.object(engine.stt, "model_ready", return_value=False))
            self._disable_tts_backend(stack, engine.tts)
            self._disable_tts_backend(stack, engine.cloud_fallback_tts)
            self._disable_tts_backend(stack, engine.fallback_tts)
            status = engine.status()

        self.assertFalse(status.input_ready)
        self.assertFalse(status.output_ready)
        self.assertFalse(status.fully_ready)

    def test_input_and_output_are_separate_capabilities(self):
        engine = VoiceEngine()
        with ExitStack() as stack:
            stack.enter_context(patch.object(engine.recorder, "dependencies_available", return_value=True))
            stack.enter_context(patch.object(engine.recorder, "is_available", return_value=True))
            stack.enter_context(patch.object(engine.recorder, "device_label", return_value="[1] Test Mic (48000 Hz)"))
            stack.enter_context(patch.object(engine.stt, "dependency_available", return_value=True))
            stack.enter_context(patch.object(engine.stt, "model_ready", return_value=True))
            self._disable_tts_backend(stack, engine.tts)
            self._disable_tts_backend(stack, engine.cloud_fallback_tts)
            self._disable_tts_backend(stack, engine.fallback_tts)
            status = engine.status()

        self.assertTrue(status.input_ready)
        self.assertFalse(status.output_ready)
        self.assertFalse(status.fully_ready)

    def test_fallback_tts_counts_as_available_output(self):
        engine = VoiceEngine()
        if engine.fallback_tts is None:
            self.skipTest("No fallback TTS configured")

        with ExitStack() as stack:
            self._disable_tts_backend(stack, engine.tts)
            self._disable_tts_backend(stack, engine.cloud_fallback_tts)
            stack.enter_context(patch.object(engine.fallback_tts, "is_available", return_value=True))
            status = engine.status()

        self.assertTrue(status.output_ready)
        self.assertTrue(status.fallback_active)
        self.assertEqual(status.tts_engine, "piper")

    def test_start_listening_stops_speech_first(self):
        engine = VoiceEngine()
        order = []
        with (
            patch.object(engine.tts, "stop", side_effect=lambda: order.append("stop_tts")),
            patch.object(engine.recorder, "start", side_effect=lambda: order.append("start_mic")),
        ):
            engine.start_listening()
        self.assertEqual(order, ["stop_tts", "start_mic"])


if __name__ == "__main__":
    unittest.main()

class VoiceEngineStrictPreviewTests(unittest.TestCase):
    def test_strict_preview_does_not_hide_primary_failure_with_fallback(self):
        from voice.errors import SpeechSynthesisUnavailableError
        engine = VoiceEngine()
        primary = engine.tts
        fallback = engine.fallback_tts
        if primary is None or fallback is None:
            self.skipTest("Primary/fallback TTS not configured")
        with (
            patch.object(engine, "_tts_available", side_effect=lambda obj: obj in (primary, fallback)),
            patch.object(primary, "speak", side_effect=SpeechSynthesisUnavailableError("primary failed")),
            patch.object(fallback, "speak") as fallback_speak,
        ):
            with self.assertRaises(SpeechSynthesisUnavailableError):
                engine.speak("test", allow_fallback=False)
            fallback_speak.assert_not_called()

    def test_normal_speech_can_use_fallback_and_records_it(self):
        from voice.errors import SpeechSynthesisUnavailableError
        engine = VoiceEngine()
        primary = engine.tts
        fallback = engine.fallback_tts
        if primary is None or fallback is None:
            self.skipTest("Primary/fallback TTS not configured")
        with (
            patch.object(engine, "_tts_available", side_effect=lambda obj: obj in (primary, fallback)),
            patch.object(primary, "speak", side_effect=SpeechSynthesisUnavailableError("primary failed")),
            patch.object(fallback, "speak") as fallback_speak,
        ):
            engine.speak("test", allow_fallback=True)
            fallback_speak.assert_called_once()
            self.assertTrue(engine._last_fallback_active)
            self.assertEqual(engine._last_engine_used, "piper")
