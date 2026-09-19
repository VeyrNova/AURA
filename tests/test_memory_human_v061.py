import tempfile
import unittest
from pathlib import Path

from database.database import Database
from memory.manager import MemoryManager
from modules.notes import NotesManager
from modules.reminders import ReminderManager
from modules.tasks import TaskManager
from core.router import ActionRouter
from security.policy_engine import SecurityPolicyEngine


class MemoryHumanV061Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "aura.db")
        self.memory = MemoryManager(self.db)
        self.router = ActionRouter(
            NotesManager(self.db), TaskManager(self.db), ReminderManager(self.db),
            SecurityPolicyEngine(self.db), memory_manager=self.memory,
        )

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_memory_listing_is_human_not_database_dump(self):
        self.memory.remember("je préfère les réponses concises", memory_type="preference")
        answer = self.router.route("LIST_MEMORIES", {})
        self.assertIn("Tu préfères les réponses concises", answer)
        self.assertNotIn("#1", answer)
        self.assertNotIn("· preference", answer)

    def test_create_memory_confirmation_is_natural(self):
        answer = self.router.route("CREATE_MEMORY", {"raw": "je préfère les réponses concises"})
        self.assertEqual(answer, "D'accord. Je retiens que tu préfères les réponses concises.")

    def test_response_style_question_is_answered_locally(self):
        self.memory.remember("je préfère les réponses concises", memory_type="preference")
        query = "Quel style de réponse devrais-tu privilégier pour moi ?"
        self.assertTrue(self.memory.can_answer_personal_question(query))
        answer = self.router.route("ANSWER_MEMORY_QUERY", {"raw": query})
        self.assertIn("Tu préfères les réponses concises", answer)
        self.assertIn("privilégier ce style", answer)

    def test_unrelated_personal_question_is_not_short_circuited(self):
        self.memory.remember("je préfère les réponses concises", memory_type="preference")
        self.assertFalse(self.memory.can_answer_personal_question("Quel est mon prénom ?"))
        self.assertFalse(self.memory.can_answer_personal_question("Comment avancer sur AURA ?"))

    def test_sensitive_memory_is_not_used_for_direct_qa(self):
        self.memory.remember("Mon mot de passe est test123!", allow_sensitive=True)
        self.assertFalse(self.memory.can_answer_personal_question("Quel est mon mot de passe ?"))


if __name__ == "__main__":
    unittest.main()
