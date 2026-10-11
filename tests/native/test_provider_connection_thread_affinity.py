import os
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEventLoop, QThread, QTimer

from aura_native.bootstrap.composition import compose_runtime
from aura_native.providers.credentials import FakeProviderCredentialStore
from aura_native.providers.connection import ProviderConnectionResult
from aura_native.ui.qt_bridge import NativeCoreBridge

ROOT = Path(__file__).resolve().parents[2]


class DelayedTester:
    def __init__(self, delay, status="ok", *, raises=False):
        self.delay = delay
        self.status = status
        self.raises = raises

    def test(self, provider_id, config=None):
        time.sleep(self.delay)
        if self.raises:
            raise RuntimeError("private diagnostic detail")
        return ProviderConnectionResult(
            provider_id,
            self.status == "ok",
            self.status,
            "Connexion réussie" if self.status == "ok" else "Clé API invalide",
            int(self.delay * 1000),
            1 if self.status == "ok" else 0,
            str((config or {}).get("selected_model", "")),
        )


class SequencedTester:
    def __init__(self):
        self._calls = 0

    def test(self, provider_id, config=None):
        self._calls += 1
        delay, status = ((0.3, "authentication_failed"), (0.05, "ok"))[self._calls - 1]
        time.sleep(delay)
        return ProviderConnectionResult(provider_id, status == "ok", status, status, int(delay * 1000))


class ProviderThreadAffinityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.temp = TemporaryDirectory()

    def tearDown(self):
        self.temp.cleanup()

    def make_bridge(self, testers, timeout=14.0):
        with patch.dict(os.environ, {"AURA_PCC_FAKE": "1"}, clear=False):
            runtime = compose_runtime(project_root=ROOT, state_dir=Path(self.temp.name))
        runtime.provider_connection_tester = testers
        runtime.start()
        bridge = NativeCoreBridge(runtime, provider_test_timeout_seconds=timeout)
        return runtime, bridge

    def make_production_composition_bridge(self, testers, timeout=14.0):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AURA_PCC_FAKE", None)
            runtime = compose_runtime(project_root=ROOT, state_dir=Path(self.temp.name))
        self.assertIsInstance(runtime.provider_connection_tester, dict)
        fake_store = FakeProviderCredentialStore()
        fake_store.set_secret("gemini", "offline-fixture")
        runtime.provider_settings_service.store = fake_store
        runtime.provider_connection_tester = testers
        runtime.start()
        return runtime, NativeCoreBridge(runtime, provider_test_timeout_seconds=timeout)

    def wait_for_results(self, bridge, calls, timeout_ms=5000):
        started = []
        finished = []
        loop = QEventLoop()
        expected = len(calls)

        bridge.providerTestStarted.connect(started.append)

        def collect(provider_id, result):
            finished.append((provider_id, dict(result)))
            if len(finished) >= expected:
                loop.quit()

        bridge.providerTestFinished.connect(collect)
        for provider_id in calls:
            bridge.testProviderConnection(provider_id)
        QTimer.singleShot(timeout_ms, loop.quit)
        loop.exec()
        return started, finished

    def spin(self, milliseconds):
        loop = QEventLoop()
        QTimer.singleShot(milliseconds, loop.quit)
        loop.exec()

    def test_delayed_500ms_reaches_gui_thread(self):
        _runtime, bridge = self.make_bridge({"gemini": DelayedTester(0.5)})
        started, finished = self.wait_for_results(bridge, ["gemini"], 3000)
        self.assertEqual(started, ["gemini"])
        self.assertEqual(finished[0][1]["status"], "ok")
        self.assertEqual(bridge._bridge_thread_id, threading.get_ident())
        self.assertEqual(bridge._last_provider_drain_thread_id, threading.get_ident())
        self.assertNotEqual(bridge._last_provider_worker_thread_id, threading.get_ident())
        self.assertEqual(QThread.currentThread(), bridge.thread())
        self.assertFalse(bridge._active_provider_test_futures)
        bridge.close()

    def test_delayed_two_seconds_reaches_gui_thread(self):
        _runtime, bridge = self.make_bridge({"ollama": DelayedTester(2.0)})
        _started, finished = self.wait_for_results(bridge, ["ollama"], 4000)
        self.assertEqual([(p, r["status"]) for p, r in finished], [("ollama", "ok")])
        bridge.close()

    def test_error_and_exception_are_delivered(self):
        _runtime, bridge = self.make_bridge({
            "gemini": DelayedTester(0.05, "authentication_failed"),
            "ollama": DelayedTester(0.05, raises=True),
        })
        _started, finished = self.wait_for_results(bridge, ["gemini", "ollama"], 2000)
        self.assertEqual({p: r["status"] for p, r in finished}, {
            "gemini": "authentication_failed",
            "ollama": "unknown_error",
        })
        self.assertNotIn("private diagnostic detail", repr(finished))
        bridge.close()

    def test_timeout_finishes_once_and_ignores_late_result(self):
        _runtime, bridge = self.make_bridge({"gemini": DelayedTester(0.35)}, timeout=0.1)
        _started, finished = self.wait_for_results(bridge, ["gemini"], 1000)
        self.assertEqual([r["status"] for _p, r in finished], ["timeout"])
        self.spin(500)
        self.assertEqual([r["status"] for _p, r in finished], ["timeout"])
        self.assertFalse(bridge._active_provider_test_futures)
        bridge.close()

    def test_new_request_supersedes_stale_result(self):
        _runtime, bridge = self.make_bridge({"gemini": SequencedTester()})
        finished = []
        bridge.providerTestFinished.connect(lambda provider_id, result: finished.append((provider_id, dict(result))))
        bridge.testProviderConnection("gemini")
        bridge.testProviderConnection("gemini")
        self.spin(600)
        self.assertEqual([(p, r["status"]) for p, r in finished], [("gemini", "ok")])
        self.assertFalse(bridge._active_provider_test_futures)
        bridge.close()

    def test_production_composition_registry_runs_two_providers_sequentially(self):
        _runtime, bridge = self.make_production_composition_bridge({
            "gemini": DelayedTester(0.05),
            "ollama": DelayedTester(0.05),
        })
        started = []
        finished = []
        bridge.providerTestStarted.connect(started.append)
        bridge.providerTestFinished.connect(lambda provider_id, result: finished.append((provider_id, dict(result))))
        for provider_id in ("gemini", "ollama"):
            loop = QEventLoop()
            bridge.providerTestFinished.connect(lambda _provider_id, _result, current=loop: current.quit())
            bridge.testProviderConnection(provider_id)
            QTimer.singleShot(2000, loop.quit)
            loop.exec()
        self.assertEqual(started, ["gemini", "ollama"])
        self.assertEqual([(p, r["status"]) for p, r in finished], [("gemini", "ok"), ("ollama", "ok")])
        bridge.close()

    def test_source_uses_gui_owned_queue_timer_and_retains_futures(self):
        source = (ROOT / "src/aura_native/ui/qt_bridge.py").read_text(encoding="utf-8")
        self.assertIn("queue.SimpleQueue()", source)
        self.assertIn("QTimer(self)", source)
        self.assertIn("_drainProviderResultQueue", source)
        self.assertIn("_active_provider_test_futures", source)
        self.assertNotIn("_providerTestWorkerResult", source)
