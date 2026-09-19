from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "ui" / "weather_workspace.py").read_text(encoding="utf-8")

class TestWeatherWorkspaceEnter3682(unittest.TestCase):
    def test_search_consumes_return_before_qdialog_accept(self):
        self.assertIn("self.search.installEventFilter(self)", SRC)
        self.assertIn("event.key() in (Qt.Key_Return, Qt.Key_Enter)", SRC)
        self.assertIn("self._run_search()", SRC)
        self.assertIn("return True", SRC)

    def test_workspace_disables_implicit_dialog_accept(self):
        self.assertIn("def accept(self):", SRC)
        self.assertIn("b.setAutoDefault(False)", SRC)
        self.assertIn("close.setAutoDefault(False)", SRC)
        self.assertIn("speak.setAutoDefault(False)", SRC)

if __name__ == "__main__":
    unittest.main()
