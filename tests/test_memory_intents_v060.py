import tempfile
import unittest
from pathlib import Path

from core.intent_manager import IntentManager
from core.router import ActionRouter
from database.database import Database
from memory.manager import MemoryManager
from modules.notes import NotesManager
from modules.reminders import ReminderManager
from modules.tasks import TaskManager
from security.policy_engine import SecurityPolicyEngine


class MemoryIntentV060Tests(unittest.TestCase):
    def setUp(self):
        self.intent = IntentManager()
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

    def test_memory_command_detection(self):
        cases = {
            "Souviens-toi que je préfère le café": "CREATE_MEMORY",
            "Que sais-tu sur moi ?": "LIST_MEMORIES",
            "Dans ta mémoire, que sais-tu sur le café ?": "SEARCH_MEMORY",
            "Oublie le souvenir #4": "FORGET_MEMORY",
            "Oublie tout ce que tu sais sur le café": "FORGET_MEMORY_ALL",
            "Oublie tout ce que tu sais sur moi": "FORGET_ALL_MEMORIES",
            "Pourquoi tu sais ça ?": "EXPLAIN_MEMORY",
            "Active le mode privé": "SET_MEMORY_PRIVATE_MODE",
            "Désactive le mode privé": "SET_MEMORY_NORMAL_MODE",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                intent, _ = self.intent.detect(text)
                self.assertEqual(intent, expected)

    def test_router_creates_lists_and_forgets_memory(self):
        response = self.router.route("CREATE_MEMORY", {"raw": "je préfère le café"})
        self.assertIn("Je retiens", response)
        listed = self.router.route("LIST_MEMORIES", {})
        self.assertIn("café", listed)
        record = self.memory.list_memories()[0]
        forgotten = self.router.route("FORGET_MEMORY", {"raw": str(record.id)})
        self.assertIn("supprimé", forgotten)
        self.assertEqual(self.memory.list_memories(), [])

    def test_private_mode_is_deterministic(self):
        enabled = self.router.route("SET_MEMORY_PRIVATE_MODE", {})
        self.assertTrue(self.memory.private_mode)
        self.assertIn("Mode privé activé", enabled)
        blocked = self.router.route("CREATE_MEMORY", {"raw": "je préfère le thé"})
        self.assertIn("mode privé", blocked.lower())
        self.router.route("SET_MEMORY_NORMAL_MODE", {})
        self.assertFalse(self.memory.private_mode)

    def test_forget_all_profile_data_preserves_tasks(self):
        self.router.route("CREATE_MEMORY", {"raw": "je préfère le café"})
        TaskManager(self.db).create_task("Conserver cette tâche")
        response = self.router.route("FORGET_ALL_MEMORIES", {})
        self.assertIn("notes, tâches et rappels n'ont pas été touchés", response)
        self.assertEqual(self.memory.list_memories(), [])
        self.assertEqual(len(TaskManager(self.db).list_tasks()), 1)


if __name__ == "__main__":
    unittest.main()
