import unittest

from consciousness.self_model import SelfModel


class SelfModelTests(unittest.TestCase):
    def test_default_capabilities_are_conservative(self):
        model = SelfModel()
        caps = model.capabilities()
        self.assertTrue(caps["notes"])
        self.assertTrue(caps["tasks"])
        self.assertTrue(caps["reminders"])
        self.assertTrue(caps["security_core"])
        self.assertTrue(caps["consciousness_core"])
        self.assertFalse(caps["voice"])
        self.assertFalse(caps["voice_input"])
        self.assertFalse(caps["voice_output"])
        self.assertFalse(caps["internet"])
        self.assertFalse(caps["system_control"])

    def test_capability_override_returns_new_model(self):
        model = SelfModel()
        newer = model.with_capability("voice", True)
        self.assertFalse(model.has_capability("voice"))
        self.assertTrue(newer.has_capability("voice"))

    def test_unknown_capability_cannot_be_created_silently(self):
        with self.assertRaises(KeyError):
            SelfModel().with_capability("telepathy", True)


if __name__ == "__main__":
    unittest.main()
