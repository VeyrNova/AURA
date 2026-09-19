from __future__ import annotations

import ast
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MAIN = ROOT / "ui" / "main_window.py"
source = MAIN.read_text(encoding="utf-8-sig", errors="replace")

for token in (
    "AURA v1.2.1 UI STT COMPLETION WATCHDOG HOTFIX",
    "class STTRecoveryWorker(QObject):",
    "self._stt_terminal_handled = False",
    "QTimer.singleShot(12000, self._stt_watchdog_tick)",
    "def _stt_watchdog_tick(self):",
    "def _stt_watchdog_fail_safe(self):",
    "def _on_stt_recovery_finished(self, text: str):",
    "def _on_stt_recovery_failed(self, message: str):",
    'event_bus.voice_status_changed.emit("IDLE")',
    "self.aura_core.voice_engine.stt = HybridSpeechToText()",
):
    assert token in source, token

tree = ast.parse(source, filename=str(MAIN))
classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
assert "STTWorker" in classes
assert "STTRecoveryWorker" in classes
assert "MainWindow" in classes

worker_segment = ast.get_source_segment(source, classes["STTWorker"]) or ""
for token in (
    "self.started = False",
    "self.done = False",
    "self.result_text =",
    "self.error_message =",
    "self.finished.emit",
    "self.failed.emit",
):
    assert token in worker_segment, token

main = classes["MainWindow"]
methods = {
    n.name: n for n in main.body
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
}
for name in (
    "_on_microphone_released",
    "_cleanup_stt_thread",
    "_cleanup_stt_recovery_thread",
    "_stt_watchdog_tick",
    "_stt_watchdog_fail_safe",
    "_on_stt_recovery_finished",
    "_on_stt_recovery_failed",
    "_on_stt_finished",
    "_on_stt_failed",
):
    assert name in methods, name

from PySide6.QtCore import QCoreApplication, QThread
from ui.main_window import STTWorker

class FakeVoiceEngine:
    def transcribe(self, audio):
        return "test vocal"

class FakeCore:
    def __init__(self):
        self.voice_engine = FakeVoiceEngine()

app = QCoreApplication.instance() or QCoreApplication([])
thread = QThread()
worker = STTWorker(FakeCore(), [0.1, -0.1])
result, errors = [], []
worker.moveToThread(thread)
thread.started.connect(worker.run)
worker.finished.connect(result.append)
worker.failed.connect(errors.append)
worker.finished.connect(thread.quit)
worker.failed.connect(thread.quit)
thread.start()

deadline = time.monotonic() + 3.0
while thread.isRunning() and time.monotonic() < deadline:
    app.processEvents()
    time.sleep(0.01)
thread.wait(1000)
app.processEvents()

assert result == ["test vocal"], result
assert errors == [], errors
assert worker.started is True
assert worker.done is True
assert worker.result_text == "test vocal"

print("[PASS] STT watchdog source contract")
print("[PASS] patched STTWorker Qt delivery")
