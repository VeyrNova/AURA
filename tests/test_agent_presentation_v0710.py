import unittest
from tools.models import ToolResult
from ui.response_presentation import for_tool_result


class AgentPresentationV0710Tests(unittest.TestCase):
    def test_agent_result_is_visual(self):
        result = ToolResult(True, "a\n\nb", "agent", "agent-kernel", item_count=2, expected_items=2, complete=True)
        decision = for_tool_result(result)
        self.assertTrue(decision.visual)
        self.assertEqual(decision.title, "PLAN AURA")
        self.assertIn("2 étapes", decision.subtitle)


if __name__ == "__main__":
    unittest.main()
