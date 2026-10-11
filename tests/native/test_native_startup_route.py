from pathlib import Path
import unittest

ROOT = Path(__file__).parents[2]


class NativeStartupRouteTests(unittest.TestCase):
    def test_main_declares_home_startup_route(self):
        source = (ROOT / "app/qml/Main.qml").read_text(encoding="utf-8")
        self.assertIn('startupRoute: "home"', source)
        self.assertIn('bridge.setWorkspace(startupRoute)', source)

    def test_bridge_default_workspace_is_home(self):
        source = (ROOT / "app/main.py").read_text(encoding="utf-8")
        self.assertIn('self._workspace="home"', source)


if __name__ == "__main__": unittest.main()
