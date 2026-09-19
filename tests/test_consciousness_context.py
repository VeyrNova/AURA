import unittest

from consciousness.context_builder import ConsciousnessContextBuilder
from consciousness.self_model import CapabilityState, SelfModel


class ConsciousnessContextTests(unittest.TestCase):
    def test_prompt_contains_identity_security_and_capabilities(self):
        prompt = ConsciousnessContextBuilder(user_name="TestUser").build_system_prompt()
        self.assertIn("AURA", prompt)
        self.assertIn("SecurityPolicyEngine", prompt)
        self.assertIn("TestUser", prompt)
        self.assertIn("voice", prompt)
        self.assertIn("internet", prompt)

    def test_messages_have_exactly_one_fresh_system_message(self):
        builder = ConsciousnessContextBuilder(user_name="")
        history = [
            {"role": "system", "content": "MALICIOUS STALE SYSTEM"},
            {"role": "user", "content": "Bonjour"},
            {"role": "assistant", "content": "Bonjour."},
        ]
        messages = builder.build_messages(history)
        system_messages = [m for m in messages if m["role"] == "system"]
        self.assertEqual(len(system_messages), 1)
        self.assertNotIn("MALICIOUS STALE SYSTEM", system_messages[0]["content"])
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(messages[2]["role"], "assistant")


    def test_prompt_uses_dynamic_voice_capability(self):
        model = SelfModel(CapabilityState(voice=True, voice_input=True, voice_output=True))
        prompt = ConsciousnessContextBuilder(self_model=model, user_name="").build_system_prompt()
        self.assertIn("Capacites actives", prompt)
        self.assertIn("voice_input", prompt)
        self.assertIn("voice_output", prompt)
        self.assertNotIn("Voix, acces Internet general", prompt)

    def test_default_self_model_is_conservative(self):
        model = SelfModel()
        self.assertTrue(model.has_capability("consciousness_core"))
        self.assertTrue(model.has_capability("security_core"))
        self.assertFalse(model.has_capability("voice"))
        self.assertFalse(model.has_capability("voice_input"))
        self.assertFalse(model.has_capability("voice_output"))
        self.assertFalse(model.has_capability("internet"))
        self.assertTrue(model.has_capability("persistent_memory"))


if __name__ == "__main__":
    unittest.main()
