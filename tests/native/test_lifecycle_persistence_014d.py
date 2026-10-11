import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from aura_native.bootstrap.composition import compose_runtime
from aura_native.config.locale_service import LocaleService
from aura_native.config.paths import PathConfigurationError, RuntimePaths
from aura_native.storage.database import NativeDatabase


ROOT = Path(__file__).parents[2]


class LifecyclePersistence014DTests(unittest.TestCase):
    def test_state_root_is_explicit_and_contained(self):
        temp = tempfile.TemporaryDirectory(prefix="aura-014d-")
        try:
            paths = RuntimePaths.resolve(temp.name, project_root=ROOT)
            self.assertEqual(paths.state_dir, Path(temp.name).resolve())
            self.assertTrue(paths.data_dir.is_relative_to(paths.state_dir))
            with self.assertRaises(PathConfigurationError):
                RuntimePaths.resolve(str(ROOT), project_root=ROOT)
        finally:
            temp.cleanup()

    def test_empty_state_composition_and_second_run(self):
        temp = tempfile.TemporaryDirectory(prefix="aura-014d-")
        try:
            state = Path(temp.name)
            first = compose_runtime(project_root=ROOT, state_dir=state)
            first.start(); first.stop()
            second = compose_runtime(project_root=ROOT, state_dir=state)
            second.start(); second.stop()
            self.assertTrue(state.is_dir())
        finally:
            temp.cleanup()

    def test_runtime_start_and_stop_are_idempotent(self):
        temp = tempfile.TemporaryDirectory(prefix="aura-014d-")
        try:
            runtime = compose_runtime(project_root=ROOT, state_dir=Path(temp.name))
            runtime.start(); runtime.start(); runtime.stop(); runtime.stop()
            self.assertEqual(runtime.state.value, "stopped")
        finally:
            temp.cleanup()

    def test_corrupt_locale_is_preserved_and_defaults_safely(self):
        temp = tempfile.TemporaryDirectory(prefix="aura-014d-")
        try:
            path = Path(temp.name) / "ui_locale.json"
            path.write_text("{not-json", encoding="utf-8")
            service = LocaleService(Path(temp.name))
            self.assertEqual(service.locale, "fr-FR")
            self.assertEqual(path.read_text(encoding="utf-8"), "{not-json")
        finally:
            temp.cleanup()

    def test_locale_write_is_atomic_and_restartable(self):
        temp = tempfile.TemporaryDirectory(prefix="aura-014d-")
        try:
            service = LocaleService(Path(temp.name))
            self.assertTrue(service.set_locale("en-US"))
            self.assertEqual(LocaleService(Path(temp.name)).locale, "en-US")
            self.assertFalse((Path(temp.name) / "ui_locale.json.tmp").exists())
        finally:
            temp.cleanup()

    def test_newer_database_schema_fails_without_downgrade(self):
        temp = tempfile.TemporaryDirectory(prefix="aura-014d-")
        try:
            db = Path(temp.name) / "aura_native.db"
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
            conn.execute("INSERT INTO schema_migrations VALUES(999, 'fixture')")
            conn.commit(); conn.close()
            with self.assertRaisesRegex(RuntimeError, "newer than supported"):
                NativeDatabase(db).connect()
            check = sqlite3.connect(db)
            try:
                self.assertEqual(check.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0], 999)
            finally:
                check.close()
        finally:
            temp.cleanup()

    def test_corrupt_database_is_not_replaced_silently(self):
        temp = tempfile.TemporaryDirectory(prefix="aura-014d-")
        try:
            db = Path(temp.name) / "aura_native.db"
            db.write_bytes(b"not a sqlite database")
            with self.assertRaises(sqlite3.DatabaseError):
                NativeDatabase(db).connect()
            self.assertEqual(db.read_bytes(), b"not a sqlite database")
        finally:
            temp.cleanup()

    def test_no_legacy_fallback_in_native_state_composition(self):
        source = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn('choices=("legacy", "native"), default="native"', source)
        self.assertIn('if args.core_mode == "native":', source)
        self.assertIn('Path(local_app_data) / "AURA-NATIVE"', source)


if __name__ == "__main__":
    unittest.main()
