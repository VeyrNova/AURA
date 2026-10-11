import unittest
from pathlib import Path
ROOT=Path(__file__).parents[2]
class PccLauncherPlatformTests(unittest.TestCase):
    def setUp(self): self.source=(ROOT/'tests/native/_evidence/provider_credentials_center_ui.py').read_text(encoding='utf-8')
    def test_launch_does_not_force_offscreen(self):
        self.assertIn("if a.headless:", self.source)
        self.assertNotIn("env.get('QT_QPA_PLATFORM','offscreen')", self.source)
    def test_headless_is_explicit(self): self.assertIn("env['QT_QPA_PLATFORM']='offscreen'", self.source)
    def test_fake_and_isolated_bootstrap(self):
        self.assertIn("'AURA_PCC_FAKE':'1'", self.source)
        self.assertIn("'AURA_PCC_CREDENTIALS_ROOT':str(state/'credentials')", self.source)
        self.assertIn("'AURA_NATIVE_WORKSPACE':'settings'", self.source)
    def test_official_entrypoint_and_no_network(self):
        self.assertIn("app/main.py", self.source)
        self.assertNotIn('urllib', self.source)
