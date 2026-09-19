from __future__ import annotations
from regression_compat import assert_version_at_least
from pathlib import Path

import json
import unittest
from unittest.mock import Mock, patch

from ai.llm_manager import GroqProvider, LLMManager, LLMProviderError
from config.settings import settings
from runtime.hybrid_runtime import choose_llm_route, choose_router_route, groq_configured
from runtime.resource_guardian import ResourceGuardian, ResourceSnapshot
from voice.hybrid_stt import HybridSpeechToText


class _FakeVoice:
    def __init__(self):
        self.released_xtts = 0
        self.released_stt = 0
        self.xtts_hot = True

    def release_xtts_model(self):
        self.released_xtts += 1
        self.xtts_hot = False
        return True

    def release_stt_model(self):
        self.released_stt += 1
        return True

    def xtts_model_loaded(self):
        return self.xtts_hot


class _FakeLLM:
    def running_model_info(self, model=None):
        return None

    def running_model_query_ok(self):
        return True

    def model_available(self, model):
        return True

    def unload(self, model=None):
        return True


class HybridRuntimeV0712Tests(unittest.TestCase):
    def test_version_and_audio_are_enabled(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.1.2")
        self.assertTrue(settings.AUDIO_RUNTIME_ENABLED)
        self.assertFalse(settings.AUDIO_RUNTIME_PAUSED)

    def test_hybrid_route_uses_groq_when_explicit_key_is_configured(self):
        with patch.object(settings, "AURA_RUNTIME_MODE", "hybrid"), \
             patch.object(settings, "GROQ_ENABLED", True), \
             patch.object(settings, "GROQ_API_KEY", "test-key"):
            route = choose_llm_route("Explique moi les ICPE", voice_output=True)
            self.assertEqual(route.provider, "groq")
            self.assertEqual(route.model, settings.GROQ_FAST_MODEL)
            self.assertTrue(route.remote)
            self.assertTrue(groq_configured())

    def test_sensitive_text_stays_local(self):
        with patch.object(settings, "AURA_RUNTIME_MODE", "hybrid"), \
             patch.object(settings, "GROQ_ENABLED", True), \
             patch.object(settings, "GROQ_API_KEY", "test-key"), \
             patch.object(settings, "HYBRID_PRIVATE_MEMORY_LOCAL_ONLY", True):
            route = choose_llm_route("mon mot de passe est secret123", voice_output=True)
            self.assertEqual(route.provider, "local")
            self.assertEqual(route.reason, "privacy-local")

    def test_router_uses_fast_groq_model(self):
        with patch.object(settings, "AURA_RUNTIME_MODE", "hybrid"), \
             patch.object(settings, "GROQ_ENABLED", True), \
             patch.object(settings, "GROQ_API_KEY", "test-key"):
            route = choose_router_route("cherche X puis montre la carte")
            self.assertEqual(route.provider, "groq")
            self.assertEqual(route.model, settings.GROQ_ROUTER_MODEL)

    def test_remote_guardian_profile_preserves_xtts_and_stt(self):
        voice = _FakeVoice()
        guardian = ResourceGuardian(_FakeLLM(), voice)
        guardian.sample = Mock(return_value=ResourceSnapshot(
            ram_used_pct=50.0, ram_total_gb=16.0, ram_available_gb=8.0,
            vram_used_mb=1900.0, vram_total_mb=6141.0, vram_used_pct=31.0,
        ))
        profile = {"provider": "groq", "model": "remote-model", "name": "groq-voice"}
        guardian.prepare_for_llm(profile)
        self.assertEqual(voice.released_xtts, 0)
        self.assertEqual(voice.released_stt, 0)
        self.assertTrue(voice.xtts_hot)

    def test_remote_realtime_dialogue_is_allowed_when_xtts_hot(self):
        voice = _FakeVoice()
        guardian = ResourceGuardian(_FakeLLM(), voice)
        guardian.sample = Mock(return_value=ResourceSnapshot(
            ram_used_pct=50.0, ram_total_gb=16.0, ram_available_gb=8.0,
            vram_used_mb=1900.0, vram_total_mb=6141.0, vram_used_pct=31.0,
        ))
        self.assertTrue(guardian.realtime_dialogue_ready({"provider": "groq", "model": "x"}))

    def test_remote_tts_handoff_never_unloads_local_models(self):
        voice = _FakeVoice()
        llm = _FakeLLM()
        llm.unload = Mock(return_value=True)
        guardian = ResourceGuardian(llm, voice)
        guardian.sample = Mock(return_value=ResourceSnapshot(
            ram_used_pct=50.0, ram_total_gb=16.0, ram_available_gb=8.0,
            vram_used_mb=1900.0, vram_total_mb=6141.0, vram_used_pct=31.0,
        ))
        guardian._last_llm_profile = {"provider": "groq", "model": "remote-model", "name": "groq-voice"}
        decision = guardian.prepare_for_tts()
        # v0.7.2.1 keeps the validated XTTS identity lock when XTTS is already
        # resident; the remote LLM itself does not justify changing AURA's voice.
        self.assertEqual(decision.backend, "xtts")
        self.assertFalse(decision.ollama_unloaded)
        self.assertEqual(voice.released_xtts, 0)
        self.assertEqual(voice.released_stt, 0)
        llm.unload.assert_not_called()

    def test_groq_nonstream_chat_parses_usage(self):
        provider = GroqProvider("https://api.groq.com/openai/v1", "test-key")
        response = Mock()
        response.status_code = 200
        response.headers = {}
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "model": "llama-3.1-8b-instant",
            "choices": [{"message": {"content": "Bonjour"}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "prompt_time": 0.01,
                "completion_time": 0.02,
                "total_time": 0.03,
            },
        }
        provider.session.post = Mock(return_value=response)
        text = provider.generate([{"role": "user", "content": "Salut"}], model="llama-3.1-8b-instant")
        self.assertEqual(text, "Bonjour")
        self.assertEqual(provider.last_metrics.output_tokens, 20)
        self.assertGreater(provider.last_metrics.tokens_per_second, 0)
        payload = provider.session.post.call_args.kwargs["json"]
        self.assertIn("max_completion_tokens", payload)
        self.assertNotIn("keep_alive", payload)

    def test_groq_429_opens_circuit(self):
        provider = GroqProvider("https://api.groq.com/openai/v1", "test-key")
        response = Mock(status_code=429, headers={"retry-after": "2"})
        provider.session.post = Mock(return_value=response)
        with self.assertRaises(LLMProviderError):
            provider.generate([{"role": "user", "content": "Salut"}], model="x")
        self.assertFalse(provider.available())

    def test_groq_base_url_is_fail_closed(self):
        with self.assertRaises(LLMProviderError):
            GroqProvider("https://example.com/openai/v1", "test-key")

    def test_groq_stt_base_url_is_fail_closed_before_audio_upload(self):
        from voice.groq_stt import GroqWhisperSTT
        with patch.object(settings, "GROQ_ENABLED", True), \
             patch.object(settings, "GROQ_API_KEY", "test-key"), \
             patch.object(settings, "GROQ_STT_ENABLED", True), \
             patch.object(settings, "GROQ_BASE_URL", "https://example.com/openai/v1"):
            stt = GroqWhisperSTT()
            self.assertFalse(stt.configured())
            self.assertFalse(stt.available())

    def test_groq_stt_429_opens_local_fallback_circuit(self):
        from voice.groq_stt import GroqWhisperSTT
        import numpy as np
        with patch.object(settings, "GROQ_ENABLED", True), \
             patch.object(settings, "GROQ_API_KEY", "test-key"), \
             patch.object(settings, "GROQ_STT_ENABLED", True), \
             patch.object(settings, "GROQ_BASE_URL", "https://api.groq.com/openai/v1"):
            stt = GroqWhisperSTT()
            response = Mock(status_code=429, headers={"retry-after": "2"})
            stt.session.post = Mock(return_value=response)
            from voice.errors import SpeechRecognitionUnavailableError
            with self.assertRaises(SpeechRecognitionUnavailableError):
                stt.transcribe(np.zeros(160, dtype=np.float32))
            self.assertFalse(stt.available())

    def test_hybrid_stt_prefers_groq_then_falls_back_local(self):
        stt = HybridSpeechToText()
        with patch.object(settings, "AURA_RUNTIME_MODE", "hybrid"), \
             patch.object(settings, "GROQ_ENABLED", True), \
             patch.object(settings, "GROQ_API_KEY", "test-key"), \
             patch.object(settings, "GROQ_STT_ENABLED", True), \
             patch.object(settings, "HYBRID_LOCAL_FALLBACK", True):
            stt.groq.transcribe = Mock(side_effect=Exception("boom"))
            # Only SpeechRecognitionUnavailableError triggers the intentional fallback.
            from voice.errors import SpeechRecognitionUnavailableError
            stt.groq.transcribe = Mock(side_effect=SpeechRecognitionUnavailableError("quota"))
            stt.local.is_available = Mock(return_value=True)
            stt.local.transcribe = Mock(return_value="bonjour aura")
            self.assertEqual(stt.transcribe([0.0]), "bonjour aura")
            self.assertEqual(stt.last_provider, "local")

    def test_llm_manager_keeps_local_resource_api_even_with_groq(self):
        with patch.object(settings, "GROQ_ENABLED", True), patch.object(settings, "GROQ_API_KEY", "test-key"):
            manager = LLMManager()
            self.assertIs(manager.provider, manager.local_provider)
            self.assertIsNotNone(manager.groq_provider)

    def test_ui_source_uses_background_xtts_and_audio_runtime_switch(self):
        source = Path("ui/main_window.py").read_text(encoding="utf-8")
        self.assertIn("XTTSBackgroundPrewarmWorker", source)
        self.assertIn("settings.AUDIO_RUNTIME_PAUSED", source)
        self.assertIn("provider=profile.get(\"provider\", \"local\")", source)


if __name__ == "__main__":
    unittest.main()
