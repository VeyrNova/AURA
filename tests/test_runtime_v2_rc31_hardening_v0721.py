from __future__ import annotations

import unittest
import sys
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from config.settings import settings
from core.version import AURA_BUILD, AURA_RELEASE_CHANNEL, AURA_VERSION
from tools.web_search import FreeWebSearchTool
from tools.search_intent import is_structured_visual_request
from voice.microphone import MicrophoneRecorder

ROOT = Path(__file__).resolve().parents[1]


class _FakeDDGSFactory:
    def __init__(self, behavior):
        self.behavior = behavior
        self.calls = []

    def __call__(self, timeout=5):
        outer = self

        class _Client:
            def text(self, query, **kwargs):
                backend = kwargs.get("backend")
                outer.calls.append(backend)
                value = outer.behavior.get(backend, [])
                if isinstance(value, BaseException):
                    raise value
                return list(value)

        return _Client()


class RuntimeV2RC31HardeningTests(unittest.TestCase):
    def test_release_identity(self):
        self.assertEqual(AURA_VERSION, "0.7.2.1")
        self.assertEqual(AURA_BUILD, "2026.08.15.9")
        self.assertEqual(AURA_RELEASE_CHANNEL, "consolidation-rc3.2")

    def test_search_backends_are_truthful_and_supported_by_observed_ddgs(self):
        src = (ROOT / "tools" / "web_search.py").read_text(encoding="utf-8", errors="replace")
        self.assertIn('(\"google\", \"duckduckgo\", \"startpage\", \"yahoo\", \"mojeek\")'.replace('\\"','"'), src)
        self.assertNotIn('\"bing\": \"Bing\"'.replace('\\"','"'), src)

    def test_legacy_bing_env_token_is_migrated_in_memory_without_bing_call(self):
        factory = _FakeDDGSFactory({"yahoo": [{"title": "Y", "href": "https://example.com/y", "body": "Y"}]})
        with patch.object(settings, "WEB_SEARCH_ENABLED", True), \
             patch.object(settings, "FREE_WEB_SEARCH_ENABLED", True), \
             patch.object(settings, "FREE_WEB_SEARCH_SYNTHESIS_ENABLED", False):
            tool = FreeWebSearchTool(backends="bing", ddgs_factory=factory)
            result = tool.execute("test", count=1)
        self.assertTrue(result.ok)
        self.assertEqual(result.data.get("backend"), "yahoo")
        self.assertEqual(factory.calls, ["yahoo"])
        self.assertNotIn("bing", tool.backends)

    def test_search_fallback_reports_the_backend_actually_requested(self):
        factory = _FakeDDGSFactory({
            "google": RuntimeError("blocked"),
            "duckduckgo": RuntimeError("limited"),
            "startpage": [],
            "yahoo": [{"title": "Result", "href": "https://example.com/x", "body": "Evidence"}],
        })
        with patch.object(settings, "WEB_SEARCH_ENABLED", True), \
             patch.object(settings, "FREE_WEB_SEARCH_ENABLED", True), \
             patch.object(settings, "FREE_WEB_SEARCH_SYNTHESIS_ENABLED", False):
            tool = FreeWebSearchTool(backends="google,duckduckgo,startpage,yahoo,mojeek", ddgs_factory=factory)
            result = tool.execute("test", count=1)
        self.assertTrue(result.ok)
        self.assertEqual(result.data.get("backend"), "yahoo")
        self.assertEqual(factory.calls, ["google", "duckduckgo", "startpage", "yahoo"])

    def test_tts_is_suppressed_while_async_voice_worker_owns_xtts(self):
        src = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8", errors="replace")
        block = src[src.index("def _speak_text("):src.index("def _cleanup_tts_thread")]
        self.assertIn("Voice Identity Lock: TTS suppressed while Camilla warms", block)
        self.assertIn("if self._xtts_local_first_preloading", block)
        self.assertLess(block.index("if self._xtts_local_first_preloading"), block.index("status = self.aura_core.voice_engine.status()"))

    def test_startup_completion_is_suppressed_after_user_interaction(self):
        src = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8", errors="replace")
        self.assertIn("_user_interacted_during_voice_warmup", src)
        self.assertIn("AURA startup completion voice suppressed: user already interacted during Camilla warmup", src)

    def test_microphone_recorder_has_guarded_refresh_without_capture(self):
        src = (ROOT / "voice" / "microphone.py").read_text(encoding="utf-8", errors="replace")
        block = src[src.index("def refresh_device_state"):src.index("def is_available")]
        self.assertIn("_terminate", block)
        self.assertIn("_initialize", block)
        self.assertNotIn("InputStream", block)
        self.assertNotIn("self.start(", block)

    def test_microphone_portaudio_refresh_is_passive_and_selects_input(self):
        calls = []
        fake_sd = SimpleNamespace(
            default=SimpleNamespace(device=(-1, -1)),
            query_devices=lambda: [
                {"name": "Microphone Array (Realtek)", "max_input_channels": 2, "default_samplerate": 44100},
            ],
            _terminate=lambda: calls.append("terminate"),
            _initialize=lambda: calls.append("initialize"),
        )
        recorder = MicrophoneRecorder(requested_device="")
        with patch.object(MicrophoneRecorder, "dependencies_available", return_value=True), \
             patch.dict(sys.modules, {"sounddevice": fake_sd}):
            selected = recorder.refresh_device_state(reinitialize_portaudio=True)
        self.assertIsNotNone(selected)
        self.assertIn("Realtek", selected.name)
        self.assertEqual(calls, ["terminate", "initialize"])
        self.assertFalse(recorder.is_recording)

    def test_ui_only_requests_portaudio_refresh_on_first_retry(self):
        src = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8", errors="replace")
        block = src[src.index("def _retry_microphone_detection"):src.index("# ------------------------------------------------------------------\n    # Text / intent / LLM")]
        self.assertIn("self._microphone_recovery_attempt == 1", block)
        self.assertIn("refresh_microphone_detection", block)
        self.assertIn("MIC_RECOVERY_PORTAUDIO_REFRESH", block)

    def test_structured_visual_budget_avoids_old_420_token_ceiling(self):
        self.assertTrue(is_structured_visual_request("affiche la discographie de Deftones"))
        self.assertGreaterEqual(settings.LLM_VISUAL_STRUCTURED_NUM_PREDICT, 800)
        src = (ROOT / "ai" / "visual_routing.py").read_text(encoding="utf-8", errors="replace")
        self.assertIn("visual-structured", src)
        self.assertIn("LLM_VISUAL_STRUCTURED_NUM_PREDICT", src)

    def test_microphone_selection_logic_remains_deterministic(self):
        devices = [
            {"name": "Stereo Mix", "max_input_channels": 2, "default_samplerate": 48000},
            {"name": "Microphone Array (Realtek)", "max_input_channels": 2, "default_samplerate": 44100},
        ]
        selected = MicrophoneRecorder.choose_input_device(devices, default_input=-1, requested="")
        self.assertIsNotNone(selected)
        self.assertIn("Microphone Array", selected.name)


if __name__ == "__main__":
    unittest.main()
