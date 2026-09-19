import unittest

from ai.llm_manager import OllamaProvider
from config.settings import settings
from consciousness.context_builder import ConsciousnessContextBuilder
from consciousness.personality import PersonalityEngine


class LatencyProfileTests(unittest.TestCase):
    def test_ollama_payload_uses_keep_alive_and_bounded_generation(self):
        provider = OllamaProvider("http://localhost:11434", "test-model")
        payload = provider._payload([{"role": "user", "content": "bonjour"}], stream=True)
        expected = settings.RESOURCE_LLM_KEEP_ALIVE_TEXT if settings.RESOURCE_GUARDIAN_ENABLED else settings.LLM_KEEP_ALIVE
        self.assertEqual(payload["keep_alive"], expected)
        self.assertTrue(payload["stream"])
        self.assertGreater(payload["options"]["num_predict"], 0)
        self.assertGreaterEqual(payload["options"]["num_ctx"], 1024)

    def test_history_is_bounded(self):
        builder = ConsciousnessContextBuilder()
        history = []
        for i in range(settings.LLM_MAX_HISTORY_MESSAGES + 10):
            history.append({"role": "user" if i % 2 == 0 else "assistant", "content": str(i)})
        messages = builder.build_messages(history)
        self.assertEqual(len(messages), 1 + settings.LLM_MAX_HISTORY_MESSAGES)
        self.assertEqual(messages[-1]["content"], str(len(history) - 1))

    def test_requested_personality_is_more_sensual_but_serious_mode_is_safe(self):
        engine = PersonalityEngine()
        normal = engine.effective_profile("NORMAL")
        serious = engine.effective_profile("SERIOUS")
        self.assertGreaterEqual(normal.sensuality, 0.60)
        self.assertGreaterEqual(normal.charisma, 0.85)
        self.assertGreaterEqual(normal.flirtation, 0.28)
        self.assertEqual(serious.flirtation, 0.0)
        self.assertLessEqual(serious.sensuality, 0.05)


if __name__ == "__main__":
    unittest.main()
