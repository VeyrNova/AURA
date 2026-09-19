from __future__ import annotations

import unittest
from unittest.mock import patch

from ai.llm_manager import DisabledLocalProvider, LLMManager, LLMProviderError
from config.settings import settings
from core.version import AURA_BUILD, AURA_VERSION
from runtime.intelligence_router import (
    choose_document_route,
    choose_llm_route,
    choose_router_route,
)
from runtime.state_manager import CANONICAL_STATES, normalize_state


class RuntimeV2FoundationTests(unittest.TestCase):
    def test_canonical_version(self):
        self.assertEqual(AURA_VERSION, "0.7.2.1")
        self.assertEqual(settings.APP_VERSION, AURA_VERSION)
        self.assertEqual(settings.APP_BUILD, AURA_BUILD)

    def test_cloud_first_groq_conversation(self):
        with patch.object(settings, "AURA_RUNTIME_MODE", "cloud"), \
             patch.object(settings, "GROQ_ENABLED", True), \
             patch.object(settings, "GROQ_API_KEY", "g" * 32), \
             patch.object(settings, "GEMINI_ENABLED", True), \
             patch.object(settings, "GEMINI_API_KEY", "m" * 32), \
             patch.object(settings, "LOCAL_LLM_ENABLED", False):
            route = choose_llm_route("Bonjour Aura", voice_output=True)
            self.assertEqual(route.provider, "groq")
            self.assertTrue(route.remote)
            self.assertTrue(route.available)

    def test_gemini_is_secondary_conversation_brain(self):
        with patch.object(settings, "AURA_RUNTIME_MODE", "cloud"), \
             patch.object(settings, "GROQ_ENABLED", False), \
             patch.object(settings, "GROQ_API_KEY", ""), \
             patch.object(settings, "GEMINI_ENABLED", True), \
             patch.object(settings, "GEMINI_API_KEY", "m" * 32), \
             patch.object(settings, "LOCAL_LLM_ENABLED", False):
            route = choose_llm_route("Explique ceci", voice_output=False)
            self.assertEqual(route.provider, "gemini")
            self.assertTrue(route.remote)

    def test_document_prefers_gemini(self):
        with patch.object(settings, "AURA_RUNTIME_MODE", "cloud"), \
             patch.object(settings, "GROQ_ENABLED", True), \
             patch.object(settings, "GROQ_API_KEY", "g" * 32), \
             patch.object(settings, "GEMINI_ENABLED", True), \
             patch.object(settings, "GEMINI_API_KEY", "m" * 32):
            route = choose_document_route("analyse le rapport")
            self.assertEqual(route.provider, "gemini")
            self.assertEqual(route.model, settings.GEMINI_DOCUMENT_MODEL)

    def test_private_request_fails_closed_when_local_disabled(self):
        with patch.object(settings, "AURA_RUNTIME_MODE", "cloud"), \
             patch.object(settings, "GROQ_ENABLED", True), \
             patch.object(settings, "GROQ_API_KEY", "g" * 32), \
             patch.object(settings, "LOCAL_LLM_ENABLED", False), \
             patch.object(settings, "HYBRID_PRIVATE_MEMORY_LOCAL_ONLY", True):
            route = choose_llm_route("mon mot de passe est secret123", voice_output=False)
            self.assertEqual(route.provider, "local")
            self.assertFalse(route.remote)
            self.assertFalse(route.available)

    def test_local_disabled_provider_does_not_require_ollama(self):
        with patch.object(settings, "LOCAL_LLM_ENABLED", False), \
             patch.object(settings, "GROQ_ENABLED", False), \
             patch.object(settings, "GEMINI_ENABLED", False):
            manager = LLMManager()
            self.assertIsInstance(manager.local_provider, DisabledLocalProvider)
            self.assertEqual(manager.running_models(), [])
            self.assertEqual(manager.local_models(), ())
            with self.assertRaises(LLMProviderError):
                manager.generate([{"role": "user", "content": "local uniquement"}], provider="local")

    def test_router_cloud_first(self):
        with patch.object(settings, "AURA_RUNTIME_MODE", "hybrid"), \
             patch.object(settings, "GROQ_ENABLED", True), \
             patch.object(settings, "GROQ_API_KEY", "g" * 32):
            route = choose_router_route("cherche ceci")
            self.assertEqual(route.provider, "groq")

    def test_state_vocabulary_and_legacy_aliases(self):
        self.assertIn("SEARCHING", CANONICAL_STATES)
        self.assertIn("WAITING_CONFIRMATION", CANONICAL_STATES)
        self.assertEqual(normalize_state("processing"), "ANALYZING")
        self.assertEqual(normalize_state("executing"), "ACTING")
        self.assertEqual(normalize_state("nonsense"), "ERROR")


if __name__ == "__main__":
    unittest.main()
