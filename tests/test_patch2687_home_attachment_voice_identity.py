from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class Patch2687Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = (ROOT/"ui"/"main_window.py").read_text(encoding="utf-8")
        cls.guardian = (ROOT/"runtime"/"resource_guardian.py").read_text(encoding="utf-8")

    def test_home_attachment_has_explicit_origin(self):
        self.assertIn('origin: str = "conversation"', self.main)
        self.assertIn('origin="home"', self.main)
        self.assertIn('origin="conversation"', self.main)

    def test_home_attachment_does_not_force_popup(self):
        self.assertIn("Document attachment retained on Home; conversation popup unchanged", self.main)
        self.assertIn('if origin == "conversation":', self.main)

    def test_document_fast_lane_preserved(self):
        self.assertIn("Document FAST lane dispatched", self.main)
        self.assertIn('provider_name == "gemini"', self.main)

    def test_remote_provider_supports_gemini(self):
        self.assertIn('in {"groq", "gemini"}', self.guardian)

    def test_voice_identity_lock_present(self):
        self.assertIn("Voice Identity Lock", self.guardian)
        self.assertIn("voice_identity_lock=True", self.guardian)

    def test_hot_xtts_bypasses_normal_reserve(self):
        hot = self.guardian.index("if xtts_hot:")
        cold = self.guardian.index("# XTTS is cold:", hot)
        segment = self.guardian[hot:cold]
        self.assertIn('return ResourceDecision("xtts"', segment)
        self.assertNotIn("_display_gpu_guard_reason", segment)

    def test_emergency_fallback_releases_xtts(self):
        self.assertIn("voice_identity_emergency=True", self.guardian)
        self.assertIn("self.voice_engine.release_xtts_model()", self.guardian)

if __name__ == "__main__":
    unittest.main()
