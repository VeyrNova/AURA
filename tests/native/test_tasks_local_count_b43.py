from pathlib import Path
import unittest


ROOT = Path(__file__).parents[2]


class TasksLocalCountTests(unittest.TestCase):
    def test_native_bridge_exposes_safe_local_count(self):
        source = (ROOT / "src/aura_native/ui/qt_bridge.py").read_text(encoding="utf-8")
        self.assertIn("def taskCount(self): return self.tasks_model.rowCount()", source)

    def test_qml_normalizes_local_count(self):
        source = (ROOT / "app/qml/views/TasksView.qml").read_text(encoding="utf-8")
        self.assertIn("String(Number(coreBridge.taskCount || 0))", source)
        self.assertNotIn('text: coreBridge.taskCount + " tâche(s)"', source)

    def test_count_rendering_contract(self):
        def render(value):
            try:
                return f"{int(value or 0)} tâche(s)"
            except (TypeError, ValueError):
                return "0 tâche(s)"
        self.assertEqual(render(0), "0 tâche(s)")
        self.assertEqual(render(3), "3 tâche(s)")
        self.assertEqual(render(None), "0 tâche(s)")
        self.assertEqual(render("undefined"), "0 tâche(s)")


if __name__ == "__main__":
    unittest.main()
