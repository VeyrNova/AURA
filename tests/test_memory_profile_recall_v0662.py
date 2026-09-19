import tempfile
import unittest
from pathlib import Path

from database.database import Database
from memory.manager import MemoryManager


class MemoryProfileRecallV0662Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "aura.db")
        self.memory = MemoryManager(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_what_do_you_know_about_me_returns_global_profile(self):
        self.memory.remember("je préfère les réponses concises", memory_type="preference", importance=4)
        query = "Que sais-tu de moi ?"
        self.assertTrue(self.memory.can_answer_personal_question(query))
        answer = self.memory.answer_personal_question(query)
        self.assertIsNotNone(answer)
        self.assertIn("tu préfères les réponses concises", answer.lower())
        self.assertIn("seul élément personnel", answer.lower())

    def test_global_profile_does_not_need_semantic_overlap(self):
        self.memory.remember("je travaille sur AURA", memory_type="project", importance=4)
        answer = self.memory.answer_personal_question("Qu'est-ce que tu as retenu de moi ?")
        self.assertIn("tu travailles sur AURA", answer)

    def test_global_profile_can_report_empty_memory_deterministically(self):
        query = "Que sais-tu de moi ?"
        self.assertTrue(self.memory.can_answer_personal_question(query))
        answer = self.memory.answer_personal_question(query)
        self.assertIn("aucun souvenir personnel", answer.lower())

    def test_sensitive_memories_are_excluded_from_global_profile(self):
        self.memory.remember("je préfère les réponses concises", memory_type="preference", importance=4)
        self.memory.remember("Mon mot de passe est ultra-secret-123", memory_type="fact", importance=5, allow_sensitive=True)
        answer = self.memory.answer_personal_question("Que sais-tu de moi ?")
        self.assertIn("réponses concises", answer)
        self.assertNotIn("ultra-secret", answer)
        self.assertNotIn("mot de passe", answer.lower())

    def test_private_mode_does_not_expose_profile(self):
        self.memory.remember("je préfère les réponses concises", memory_type="preference")
        self.memory.set_private_mode(True)
        self.assertFalse(self.memory.can_answer_personal_question("Que sais-tu de moi ?"))
        self.assertIsNone(self.memory.answer_personal_question("Que sais-tu de moi ?"))


if __name__ == "__main__":
    unittest.main()
