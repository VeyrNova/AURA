import os
import subprocess
import sys
import threading
import unittest
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from aura_native.bootstrap.composition import compose_runtime
from aura_native.core.contracts import Event
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
class QtNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtGui import QGuiApplication
        cls.QGuiApplication=QGuiApplication; cls.app=QGuiApplication.instance() or QGuiApplication([])
    def test_worker_event_is_applied_on_gui_thread(self):
        from aura_native.ui.qt_dispatcher import QtBusDispatcher
        from aura_native.ui.qt_bridge import NativeCoreBridge
        runtime=compose_runtime(project_root=ROOT,state_dir=ROOT/'tests/native/_evidence/unused-profile'); runtime.start(); dispatcher=QtBusDispatcher(runtime.bus); bridge=NativeCoreBridge(runtime)
        observed=[]; bridge.availabilityChanged.connect(lambda: observed.append(threading.get_ident()))
        worker=threading.Thread(target=lambda:runtime.bus.publish(Event(name='command.result',payload={'status':'not_migrated'}))); worker.start();worker.join()
        for _ in range(10): self.app.processEvents()
        self.assertEqual(observed,[threading.get_ident()]); self.assertEqual(bridge.availability,'not_migrated'); dispatcher.close();bridge.close()
    def test_main_qml_loads_in_native_mode(self):
        env=dict(os.environ); env['QT_QPA_PLATFORM']='offscreen'; env['PYTHONPATH']=str(ROOT/'src'); env['PYTHONDONTWRITEBYTECODE']='1'
        completed=subprocess.run([sys.executable, '-B', str(ROOT/'app/main.py'), '--core-mode','native','--state-dir',str(ROOT/'tests/native/_evidence/unused-profile'),'--qml-self-check'], cwd=ROOT, env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(completed.returncode,0,completed.stderr)
