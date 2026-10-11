from pathlib import Path
import unittest

ROOT = Path(__file__).parents[2]


class B44OAuthCompositionTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "src/aura_native/bootstrap/composition.py").read_text(encoding="utf-8")

    def test_env_override_precedes_state_owned_candidates(self):
        self.assertIn('os.environ.get("AURA_GOOGLE_OAUTH_CLIENT_FILE", "").strip()', self.source)
        self.assertIn('if not client_file:', self.source)

    def test_only_state_dir_owned_candidates_are_discovered(self):
        self.assertIn('paths.config_dir / "credentials"', self.source)
        self.assertIn('google_aura_desktop.json', self.source)
        self.assertNotIn("AURA GPT version", self.source)

    def test_no_configuration_keeps_fake_provider_non_connected(self):
        self.assertIn("FakeCalendarProvider(), FakeTasksProvider()", self.source)
        bridge = (ROOT / "src/aura_native/ui/qt_bridge.py").read_text(encoding="utf-8")
        self.assertIn('provider.__class__.__name__ == "FakeCalendarProvider"', bridge)


if __name__ == "__main__":
    unittest.main()
