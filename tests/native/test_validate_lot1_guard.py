import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

try:
    from validate_lot1 import AuditGuard
except ModuleNotFoundError:
    from tests.native.validate_lot1 import AuditGuard


class AuditGuardScratchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configured = os.environ.get("AURA_LOT1_HARNESS_SCRATCH")
        cls._owned_temp = None if configured else tempfile.TemporaryDirectory(prefix="lot1-guard-")
        cls.root = Path(configured or cls._owned_temp.name).resolve()

    @classmethod
    def tearDownClass(cls):
        if cls._owned_temp is not None:
            cls._owned_temp.cleanup()

    def guard(self):
        return AuditGuard(harness_scratch_roots=(self.root,))

    def test_mkdir_inside_scratch_is_allowed(self):
        self.guard()("os.mkdir", (self.root / "child", 0o700, -1))

    def test_mkdir_outside_scratch_is_denied(self):
        with self.assertRaises(PermissionError):
            self.guard()("os.mkdir", (self.root.parent / "outside", 0o700, -1))

    def test_state_directory_mkdir_is_denied(self):
        state = self.root.parents[2] / "_lot1-state"
        with self.assertRaises(PermissionError):
            self.guard()("os.mkdir", (state, 0o700, -1))

    def test_sqlite_connect_remains_denied(self):
        with self.assertRaises(PermissionError):
            self.guard()("sqlite3.connect", (str(self.root / "test.sqlite"),))

    def test_explicit_exclusive_file_is_allowed(self):
        guard = self.guard()
        target = self.root / "allowed.json"
        guard.allowed_writes.add(target)
        guard("open", (str(target), "x", os.O_WRONLY | os.O_CREAT | os.O_EXCL))

    def test_traversal_outside_scratch_is_denied(self):
        with self.assertRaises(PermissionError):
            self.guard()("os.mkdir", (self.root / ".." / "escape", 0o700, -1))

    def test_temporary_directory_under_installed_guard(self):
        with tempfile.TemporaryDirectory(dir=self.root) as path:
            self.assertTrue(Path(path).is_dir())
        self.assertFalse(Path(path).exists())


if __name__ == "__main__":
    unittest.main()
