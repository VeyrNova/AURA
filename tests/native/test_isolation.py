import ast
import os
from pathlib import Path
import runpy
import sys
import threading
import tempfile
import shutil
import sys
import unittest
from unittest.mock import patch

from aura_native.bootstrap.composition import compose_runtime


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src/aura_native"
GOOGLE_RUNTIME_DEPENDENCIES = {
    "requests", "httplib2", "google_auth_httplib2", "googleapiclient",
}


def _is_qt_adapter(relative: Path) -> bool:
    parts = relative.parts
    return (
        "ui" in parts
        or relative.name in {"qt_bridge.py", "qt_models.py", "day_bridge.py", "day_summary_bridge.py", "tray_service.py", "window_state.py", "windows_notifier.py"}
        or relative.as_posix() in {"location/service.py", "reminders/reminder_scheduler.py"}
    )


def _is_runtime_adapter_import(name: str) -> bool:
    parts = name.split(".")
    return (
        "ui" in parts
        or any(part in {"qt_bridge", "qt_models", "day_bridge", "day_summary_bridge", "tray_service", "windows_notifier"} for part in parts)
    )


def import_allowed(relative: Path, node, name: str) -> bool:
    if isinstance(node, ast.ImportFrom) and node.level > 0:
        return True
    root = name.split(".")[0]
    if root in sys.stdlib_module_names:
        return True
    if name.startswith("aura_native"):
        if relative.parts and relative.parts[0] == "core" and _is_runtime_adapter_import(name):
            return False
        return True
    if root == "PySide6" and _is_qt_adapter(relative):
        return True
    if relative.as_posix() == "google/transport.py" and root in GOOGLE_RUNTIME_DEPENDENCIES:
        return True
    if relative.as_posix() == "diagnostics/service.py" and root == "psutil":
        return True
    return False
if sys.flags.no_site:
    _STRICT_SCRATCH = Path(os.environ["AURA_LOT1_HARNESS_SCRATCH"]).resolve()
    _STATE_TMP = tempfile.TemporaryDirectory(prefix="isolation-", dir=_STRICT_SCRATCH)
    STATE = ROOT / "tests" / "native" / "_lot1-strict-isolation-state"
else:
    _STATE_TMP = tempfile.TemporaryDirectory(prefix="aura-isolation-")
    STATE = Path(_STATE_TMP.name) / "state"


class IsolationTests(unittest.TestCase):
    def setUp(self):
        global STATE, _STATE_TMP
        if sys.flags.no_site:
            token = Path(_STATE_TMP.name).name
            STATE = ROOT / "tests" / "native" / ("_lot1-strict-state-" + token + "-" + str(id(self)))
        else:
            STATE = Path(_STATE_TMP.name) / ("state-" + str(threading.get_ident()) + "-" + str(id(self)))
    def test_source_imports_are_stdlib_or_native(self):
        for file in PACKAGE.rglob("*.py"):
            relative = file.relative_to(PACKAGE)
            tree = ast.parse(file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    with self.subTest(file=file.name, module=name):
                        self.assertTrue(import_allowed(relative, node, name))


class StaticImportContractTests(unittest.TestCase):
    def setUp(self):
        global STATE, _STATE_TMP
        for name in list(sys.modules):
            if name.split(".")[0] in {"PySide6", "shiboken6"}:
                sys.modules.pop(name, None)
        if sys.flags.no_site:
            token = Path(_STATE_TMP.name).name
            STATE = ROOT / "tests" / "native" / ("_lot1-strict-state-" + token + "-" + str(id(self)))
        else:
            STATE = Path(_STATE_TMP.name) / ("state-" + str(threading.get_ident()) + "-" + str(id(self)))

    def allowed(self, source, relative):
        tree = ast.parse(source)
        node = next(n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)))
        name = node.names[0].name if isinstance(node, ast.Import) else (node.module or node.names[0].name)
        return import_allowed(Path(relative), node, name)

    def test_core_stdlib_allowed(self): self.assertTrue(self.allowed("import json", "core/example.py"))
    def test_core_native_allowed(self): self.assertTrue(self.allowed("from aura_native.core import runtime", "core/example.py"))
    def test_core_requests_denied(self): self.assertFalse(self.allowed("import requests", "core/example.py"))
    def test_qt_adapter_allowed(self): self.assertTrue(self.allowed("from PySide6.QtCore import QObject", "mail/qt_bridge.py"))
    def test_google_adapter_allowed(self): self.assertTrue(self.allowed("from googleapiclient.discovery import build", "google/transport.py"))
    def test_relative_models_allowed(self): self.assertTrue(self.allowed("from .models import Item", "mail/service.py"))
    def test_relative_parent_allowed(self): self.assertTrue(self.allowed("from ..service import Service", "mail/qt_bridge.py"))
    def test_core_cannot_import_qt_adapter_dependency(self): self.assertFalse(self.allowed("from PySide6.QtCore import QObject", "core/runtime.py"))
    def test_core_cannot_import_runtime_adapter(self): self.assertFalse(self.allowed("from aura_native.mail.qt_bridge import MailBridge", "core/runtime.py"))

    def test_loaded_modules_have_no_historical_or_qt_packages(self):
        # LOT 1 requires the core path to stay Qt-free. Later LOTs intentionally
        # load the dedicated Qt boundary, so distinguish an explicit UI load
        # from an accidental core dependency.
        historical = {
            "core", "ui", "runtime", "aura", "accounts", "integrations",
            "voice", "ai", "agent", "memory", "database", "dotenv", "vlc",
        }
        self.assertEqual(
            sorted(n for n in sys.modules if n.split(".")[0] in historical),
            [],
        )

        qt_roots = {"PySide6", "PyQt6", "shiboken6"}
        loaded_qt = sorted(n for n in sys.modules if n.split(".")[0] in qt_roots)
        qt_bridge_loaded = "aura_native.ui.qt_bridge" in sys.modules

        if qt_bridge_loaded:
            self.assertFalse(any(n.split(".")[0] == "PyQt6" for n in loaded_qt))
        else:
            self.assertEqual(loaded_qt, [])

        self.assertEqual(
            [n for n in sys.modules if "webengine" in n.lower() or "mainwindow" in n.lower()],
            [],
        )

    def test_loaded_native_origins_are_inside_new_package(self):
        for name, module in list(sys.modules.items()):
            if name == "aura_native" or name.startswith("aura_native."):
                with self.subTest(module=name):
                    if getattr(module, "__file__", None):
                        self.assertTrue(Path(module.__file__).resolve().is_relative_to(PACKAGE))

    def test_importing_launcher_does_not_start_or_change_paths(self):
        before = list(sys.path)
        with patch.object(Path, "mkdir", side_effect=AssertionError("unexpected mkdir")):
            namespace = runpy.run_path(str(ROOT / "tools/native_core_selfcheck.py"), run_name="native_launcher_import_test")
        self.assertTrue(callable(namespace["main"]))
        self.assertEqual(sys.path, before)
        if STATE.exists():
            shutil.rmtree(STATE)

    def test_runtime_creates_no_threads_or_state(self):
        qt_modules_before = {name for name in sys.modules if name.split(".")[0] in {"PySide6", "shiboken6"}}
        before = {thread.ident for thread in threading.enumerate()}
        runtime = compose_runtime(project_root=ROOT, state_dir=STATE)
        runtime.start()
        runtime.stop()
        self.assertEqual({thread.ident for thread in threading.enumerate()}, before)
        if STATE.exists():
            shutil.rmtree(STATE)
        self.assertFalse(STATE.exists())
        for name in list(sys.modules):
            if name.split(".")[0] in {"PySide6", "shiboken6"} and name not in qt_modules_before:
                sys.modules.pop(name, None)

    def test_legacy_environment_is_not_consumed(self):
        values = {key: "unread-sentinel" for key in ("AURA_ROOT", "AURA_UI_ROOT", "LOCALAPPDATA", "APPDATA")}
        with patch.dict(os.environ, values):
            runtime = compose_runtime(project_root=ROOT, state_dir=STATE)
            self.assertEqual(runtime.settings.profile, "native-foundation")
            self.assertEqual(runtime.paths.state_dir, STATE)

    def test_runtime_does_not_read_configuration_files(self):
        with patch.object(Path, "read_text", side_effect=AssertionError("unexpected configuration read")):
            runtime = compose_runtime(project_root=ROOT, state_dir=STATE)
            runtime.start()
            runtime.stop()

