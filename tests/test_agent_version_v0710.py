import unittest
from config.settings import settings
from consciousness.self_model import CapabilityState


class AgentVersionV0710Tests(unittest.TestCase):
    def test_version_and_capability(self):
        self.assertTrue(settings.APP_VERSION == "0.7.2")
        self.assertTrue(settings.AGENT_KERNEL_ENABLED)
        self.assertTrue(CapabilityState(agent_kernel=True).agent_kernel)


if __name__ == "__main__":
    unittest.main()
