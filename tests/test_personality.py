import unittest

from consciousness.personality import PersonalityEngine


class PersonalityTests(unittest.TestCase):
    def test_default_profile_matches_aura_identity(self):
        p = PersonalityEngine().effective_profile("NORMAL")
        self.assertGreater(p.empathy, 0.7)
        self.assertGreater(p.charisma, 0.7)
        self.assertLess(p.flirtation, 0.4)

    def test_serious_mode_removes_flirt_and_sarcasm(self):
        p = PersonalityEngine().effective_profile("SERIOUS")
        self.assertEqual(p.flirtation, 0.0)
        self.assertEqual(p.sarcasm, 0.0)
        self.assertLessEqual(p.sensuality, 0.05)

    def test_unknown_mode_falls_back_to_normal(self):
        engine = PersonalityEngine()
        self.assertEqual(engine.effective_profile("UNKNOWN"), engine.effective_profile("NORMAL"))


if __name__ == "__main__":
    unittest.main()
