import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config.settings import settings
from database.database import Database
from memory.continuity import ContinuityEngine
from memory.manager import MemoryManager
from memory.relationship import RelationshipModel


class MemoryV060Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "aura.db")
        self.memory = MemoryManager(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_schema_migration_has_v060_columns(self):
        cols = {row["name"] for row in self.db.conn.execute("PRAGMA table_info(memories)").fetchall()}
        for name in {
            "updated_at", "normalized_content", "status", "access_count",
            "last_used_context_at", "is_sensitive", "tags",
        }:
            self.assertIn(name, cols)

    def test_explicit_memory_is_persistent_and_deduplicated(self):
        first, created1 = self.memory.remember("Je préfère le café sans sucre", importance=4)
        second, created2 = self.memory.remember("Je préfère le café sans sucre", importance=3)
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(first.id, second.id)
        self.assertEqual(len(self.memory.list_memories()), 1)

    def test_relevant_memory_is_retrieved(self):
        self.memory.remember("Je préfère le café sans sucre", memory_type="preference")
        self.memory.remember("Je travaille sur le projet AURA", memory_type="project")
        records = self.memory.retrieve_for_context("Quel café pourrais-tu me conseiller ?", limit=3)
        self.assertTrue(records)
        self.assertIn("café", records[0].content.lower())

    def test_sensitive_memory_is_not_automatically_injected(self):
        record, _ = self.memory.remember("Mon mot de passe est azerty", allow_sensitive=True)
        self.assertTrue(record.is_sensitive)
        with patch.object(settings, "MEMORY_ALLOW_SENSITIVE_CONTEXT", False):
            records = self.memory.retrieve_for_context("Quel est mon mot de passe ?", limit=5)
        self.assertEqual(records, [])

    def test_auto_capture_is_conservative(self):
        with patch.object(settings, "MEMORY_AUTO_CAPTURE", True):
            record = self.memory.auto_capture("Je préfère les réponses courtes")
            ignored = self.memory.auto_capture("Il fait beau aujourd'hui")
        self.assertIsNotNone(record)
        self.assertEqual(record.type, "preference")
        self.assertIsNone(ignored)

    def test_auto_capture_refuses_sensitive_text(self):
        with patch.object(settings, "MEMORY_AUTO_CAPTURE", True):
            record = self.memory.auto_capture("Je préfère que mon mot de passe soit secret")
        self.assertIsNone(record)
        self.assertEqual(self.memory.list_memories(), [])

    def test_private_mode_blocks_creation_and_retrieval(self):
        self.memory.remember("Je travaille sur AURA", memory_type="project")
        self.memory.set_private_mode(True)
        self.assertEqual(self.memory.retrieve_for_context("AURA"), [])
        with self.assertRaises(RuntimeError):
            self.memory.remember("Je préfère le thé")

    def test_forget_deletes_local_record(self):
        record, _ = self.memory.remember("Je préfère le café")
        removed = self.memory.forget(str(record.id))
        self.assertEqual([r.id for r in removed], [record.id])
        self.assertIsNone(self.memory.get(record.id))

    def test_explain_tracks_last_injected_memories(self):
        record, _ = self.memory.remember("Je travaille sur AURA", memory_type="project")
        retrieved = self.memory.retrieve_for_context("Comment avancer sur AURA ?")
        self.assertTrue(retrieved)
        explained = self.memory.explain_last_context()
        self.assertIn(record.id, [r.id for r in explained])

    def test_continuity_stores_metadata_not_transcript(self):
        continuity = ContinuityEngine(self.db)
        sid = continuity.start_session()
        continuity.record_user_message()
        continuity.record_assistant_message()
        continuity.end_session()
        row = self.db.conn.execute("SELECT * FROM conversation_sessions WHERE id=?", (sid,)).fetchone()
        self.assertEqual(row["user_messages"], 1)
        self.assertEqual(row["assistant_messages"], 1)
        cols = {r["name"] for r in self.db.conn.execute("PRAGMA table_info(conversation_sessions)").fetchall()}
        self.assertNotIn("transcript", cols)
        self.assertNotIn("content", cols)

    def test_continuity_private_mode_stops_counters(self):
        continuity = ContinuityEngine(self.db)
        sid = continuity.start_session()
        continuity.set_private_mode(True)
        continuity.record_user_message()
        row = self.db.conn.execute("SELECT * FROM conversation_sessions WHERE id=?", (sid,)).fetchone()
        self.assertEqual(row["user_messages"], 0)
        self.assertEqual(row["private_mode"], 1)

    def test_relationship_model_is_bounded(self):
        model = RelationshipModel(self.db)
        model.start_session()
        for _ in range(300):
            model.record_user_message()
        self.assertGreaterEqual(model.familiarity, 0.10)
        self.assertLessEqual(model.familiarity, 0.95)
        prompt = model.render_for_prompt()
        self.assertIn("Familiarite fonctionnelle", prompt)
        self.assertIn("dependance", prompt)


if __name__ == "__main__":
    unittest.main()
