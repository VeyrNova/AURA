import tempfile
import unittest
from pathlib import Path

from core.router import ActionRouter
from database.database import Database
from modules.notes import NotesManager
from modules.reminders import ReminderManager
from modules.tasks import TaskManager
from security.policy_engine import SecurityPolicyEngine


class RouterSecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "test.db")
        self.security = SecurityPolicyEngine(self.db)
        self.router = ActionRouter(
            NotesManager(self.db),
            TaskManager(self.db),
            ReminderManager(self.db),
            self.security,
        )

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_create_note_still_works_through_security(self):
        response = self.router.route("CREATE_NOTE", {"raw": "note de securite"})
        self.assertIn("C'est noté", response)
        row = self.db.conn.execute("SELECT content FROM notes").fetchone()
        self.assertEqual(row["content"], "note de securite")

    def test_unknown_action_does_not_reach_a_module(self):
        response = self.router.route("UNKNOWN_ACTION", {})
        self.assertIn("pas autorisée", response)

    def test_audit_row_is_created(self):
        self.router.route("LIST_NOTES", {})
        row = self.db.conn.execute(
            "SELECT action, risk, allowed FROM security_audit ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.assertEqual(row["action"], "LIST_NOTES")
        self.assertEqual(row["risk"], "SAFE")
        self.assertEqual(row["allowed"], 1)


if __name__ == "__main__":
    unittest.main()
