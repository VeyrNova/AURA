from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QCoreApplication

from aura_native.bootstrap.composition import compose_runtime
from aura_native.ui.qt_bridge import NativeCoreBridge

ROOT = Path(__file__).resolve().parents[2]

class NativeMemoryQtBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aura-native-memory-qt-")
        self.runtime = compose_runtime(project_root=ROOT, state_dir=Path(self.temp.name))
        self.runtime.start()
        self.bridge = NativeCoreBridge(self.runtime)

    def tearDown(self):
        self.bridge.close()
        self.temp.cleanup()

    def _drain(self):
        self.runtime.bus.drain()
        self.app.processEvents()

    def test_create_list_search_and_forget_through_bridge(self):
        self.assertTrue(self.bridge.memoryAvailable)
        self.assertTrue(self.bridge.createMemory("AURA utilise une mémoire locale native"))
        self._drain()
        self.assertEqual(self.bridge.memoryCount, 1)
        memory_id = self.bridge.memories[0]["memory_id"]

        self.bridge.searchMemories("mémoire locale")
        self._drain()
        self.assertEqual(self.bridge.memoryCount, 1)

        self.assertTrue(self.bridge.forgetMemory(memory_id))
        self._drain()
        self.assertEqual(self.bridge.memoryCount, 0)

    def test_empty_memory_is_rejected(self):
        self.assertFalse(self.bridge.createMemory("   "))
        self.assertEqual(self.bridge.memoryStatus, "empty")

    def test_refresh_uses_native_memory_service(self):
        self.bridge.createMemory("Souvenir persistant pendant le runtime")
        self._drain()
        self.bridge.refreshMemories()
        self._drain()
        self.assertEqual(self.bridge.memoryCount, 1)

if __name__ == "__main__":
    unittest.main()
