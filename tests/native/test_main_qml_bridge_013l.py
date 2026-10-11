import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).parents[2]


class MainQmlBridge013LTests(unittest.TestCase):
    def test_real_main_qml_variant_map_reaches_pyside(self):
        os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ["AURA_PTT_DIAGNOSTICS"] = "1"
        state_dir = Path(tempfile.mkdtemp(prefix="aura-lot013l-state-"))
        wav_path = state_dir / "AURA_LOT013L_A.wav"
        wav_path.write_bytes(b"RIFF" + b"\x00" * 32)
        sys.path.insert(0, str(ROOT / "app"))
        sys.argv = [
            "main.py", "--core-mode", "native", "--windowed",
            "--state-dir", str(state_dir), "--qml-self-check",
        ]

        from PySide6.QtWidgets import QApplication
        from PySide6.QtQml import QQmlApplicationEngine

        observed = {}
        original_load = QQmlApplicationEngine.load

        def load_and_emit(engine, url):
            result = original_load(engine, url)
            root_objects = engine.rootObjects()
            self.assertTrue(root_objects)
            core_bridge = engine.rootContext().contextProperty("coreBridge")
            bridge = engine.rootContext().contextProperty("bridge")
            self.assertIsNotNone(core_bridge)
            self.assertIsNotNone(bridge)
            core_bridge.intentRequested.emit(
                "MUSIC_PLAY", {"query": str(wav_path)}
            )
            app = QApplication.instance()
            for _ in range(8):
                app.processEvents()
            observed["context"] = dict(getattr(bridge, "_navigation_context", {}))
            observed["root_count"] = len(root_objects)
            return result

        original_exec = QApplication.exec
        try:
            with patch.object(QQmlApplicationEngine, "load", load_and_emit), \
                 patch.object(QApplication, "exec", lambda self: 0):
                import main as native_main
                self.assertEqual(native_main.main(), 0)
        finally:
            QApplication.exec = original_exec

        self.assertEqual(observed["root_count"], 1)
        self.assertEqual(observed["context"].get("query"), str(wav_path))


if __name__ == "__main__":
    unittest.main()
