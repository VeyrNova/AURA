from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aura_native.bootstrap.composition import compose_runtime
from aura_native.core.contracts import CapabilityState, Command

ROOT = Path(__file__).resolve().parents[2]

class NativeMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aura-native-memory-")
        self.state = Path(self.temp.name)
        self.runtime = compose_runtime(project_root=ROOT, state_dir=self.state)
        self.runtime.start()

    def tearDown(self):
        self.runtime.stop()
        self.temp.cleanup()

    def _events(self, name):
        seen = []
        self.runtime.bus.subscribe(seen.append, name=name)
        return seen

    def _command(self, name, payload=None, session="test-session"):
        return Command(name=name, payload=payload or {}, session_id=session, source="test")

    def test_storage_and_memory_capabilities_are_available(self):
        states = {c.name: c.state for c in self.runtime.capabilities}
        self.assertEqual(states["storage"], CapabilityState.AVAILABLE)
        self.assertEqual(states["memory"], CapabilityState.AVAILABLE)

    def test_database_is_lazy_until_first_memory_operation(self):
        db_path = self.state / "data" / "aura_native.db"
        self.assertFalse(db_path.exists())
        self.runtime.bus.submit(self._command("memory.list"))
        self.runtime.bus.drain()
        self.assertTrue(db_path.exists())

    def test_create_and_list_memory(self):
        created = self._events("memory.created")
        listed = self._events("memory.listed")
        self.runtime.bus.submit(self._command("memory.create", {"content": "Je prefere les reponses concises", "memory_type": "preference"}))
        self.runtime.bus.drain()
        self.assertEqual(len(created), 1)
        self.runtime.bus.submit(self._command("memory.list"))
        self.runtime.bus.drain()
        self.assertEqual(listed[-1].payload["count"], 1)

    def test_duplicate_content_is_not_duplicated(self):
        updated = self._events("memory.updated")
        payload = {"content": "Projet AURA natif", "memory_type": "project"}
        self.runtime.bus.submit(self._command("memory.create", payload))
        self.runtime.bus.drain()
        self.runtime.bus.submit(self._command("memory.create", payload))
        self.runtime.bus.drain()
        self.assertEqual(len(updated), 1)
        listed = self._events("memory.listed")
        self.runtime.bus.submit(self._command("memory.list"))
        self.runtime.bus.drain()
        self.assertEqual(listed[-1].payload["count"], 1)

    def test_search_is_local_and_deterministic(self):
        found = self._events("memory.search_completed")
        self.runtime.bus.submit(self._command("memory.create", {"content": "Le projet AURA utilise Qt", "memory_type": "project"}))
        self.runtime.bus.submit(self._command("memory.create", {"content": "Je prefere le cafe", "memory_type": "preference"}))
        self.runtime.bus.drain()
        self.runtime.bus.submit(self._command("memory.search", {"query": "AURA Qt"}))
        self.runtime.bus.drain()
        self.assertEqual(found[-1].payload["count"], 1)
        self.assertIn("AURA", found[-1].payload["memories"][0]["content"])

    def test_sensitive_memory_is_hidden_by_default(self):
        listed = self._events("memory.listed")
        self.runtime.bus.submit(self._command("memory.create", {"content": "Mon mot de passe est exemple", "memory_type": "note"}))
        self.runtime.bus.drain()
        self.runtime.bus.submit(self._command("memory.list"))
        self.runtime.bus.drain()
        self.assertEqual(listed[-1].payload["count"], 0)
        self.runtime.bus.submit(self._command("memory.list", {"include_sensitive": True}))
        self.runtime.bus.drain()
        self.assertEqual(listed[-1].payload["count"], 1)
        self.assertTrue(listed[-1].payload["memories"][0]["is_sensitive"])

    def test_forget_deletes_the_memory(self):
        created = self._events("memory.created")
        forgotten = self._events("memory.forgotten")
        self.runtime.bus.submit(self._command("memory.create", {"content": "Souvenir a oublier"}))
        self.runtime.bus.drain()
        memory_id = created[-1].payload["memory"]["memory_id"]
        self.runtime.bus.submit(self._command("memory.forget", {"memory_id": memory_id}))
        self.runtime.bus.drain()
        self.assertEqual(forgotten[-1].payload["memory_id"], memory_id)
        listed = self._events("memory.listed")
        self.runtime.bus.submit(self._command("memory.list", {"include_sensitive": True}))
        self.runtime.bus.drain()
        self.assertEqual(listed[-1].payload["count"], 0)

    def test_session_memory_can_be_cleared_without_user_memory(self):
        self.runtime.bus.submit(self._command("memory.create", {"content": "Memoire utilisateur"}))
        self.runtime.bus.submit(self._command("memory.create", {"content": "Memoire session", "scope": "session"}, session="S1"))
        self.runtime.bus.drain()
        cleared = self._events("memory.session_cleared")
        self.runtime.bus.submit(self._command("memory.clear_session", {"session_id": "S1"}, session="S1"))
        self.runtime.bus.drain()
        self.assertEqual(cleared[-1].payload["count"], 1)
        listed = self._events("memory.listed")
        self.runtime.bus.submit(self._command("memory.list"))
        self.runtime.bus.drain()
        self.assertEqual(listed[-1].payload["count"], 1)

    def test_restart_rebinds_memory_handlers(self):
        self.runtime.stop()
        self.runtime.start()
        listed = self._events("memory.listed")
        self.runtime.bus.submit(self._command("memory.list"))
        self.runtime.bus.drain()
        self.assertEqual(listed[-1].payload["count"], 0)

    def test_invalid_memory_is_rejected_without_crash(self):
        self.runtime.bus.submit(self._command("memory.create", {"content": "", "memory_type": "fact"}))
        failures = self.runtime.bus.drain()
        self.assertEqual(failures, ())

if __name__ == "__main__":
    unittest.main()
