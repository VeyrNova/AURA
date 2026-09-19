import unittest

from consciousness.context_builder import ConsciousnessContextBuilder
from consciousness.self_model import SelfModel


class MemoryContextV060Tests(unittest.TestCase):
    def test_memory_sections_are_injected_into_system_prompt(self):
        builder = ConsciousnessContextBuilder(self_model=SelfModel(), user_name="Alex")
        messages = builder.build_messages(
            [{"role": "user", "content": "Parle-moi de mon café"}],
            memory_context="MEMOIRE LONG TERME PERTINENTE\n- Je préfère le café sans sucre.",
            continuity_context="CONTINUITE DE SESSION\n- Session précédente hier.",
            relationship_context="RELATIONSHIP MODEL\n- Familiarité fonctionnelle : 0.20/1.00.",
        )
        system = messages[0]["content"]
        self.assertIn("AURA CONSCIOUSNESS CORE v0.7.0", system)
        self.assertIn("Je préfère le café sans sucre", system)
        self.assertIn("Session précédente hier", system)
        self.assertIn("Familiarité fonctionnelle", system)
        self.assertIn("mode prive", system.lower())


if __name__ == "__main__":
    unittest.main()
