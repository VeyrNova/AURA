import unittest
from pathlib import Path


class LLMThreadBoundaryV061Tests(unittest.TestCase):
    def test_worker_does_not_build_sqlite_backed_context(self):
        source = (Path(__file__).resolve().parents[1] / "ui" / "main_window.py").read_text(encoding="utf-8")
        worker_block = source.split("class LLMWorker", 1)[1].split("class STTWorker", 1)[0]
        self.assertNotIn("build_llm_messages()", worker_block)
        self.assertIn("self.messages", worker_block)

    def test_main_thread_prepares_context_before_worker(self):
        source = (Path(__file__).resolve().parents[1] / "ui" / "main_window.py").read_text(encoding="utf-8")
        handler = source.split("def _on_user_message", 1)[1].split("def _on_llm_partial", 1)[0]
        build_pos = handler.index("build_llm_messages(")
        worker_pos = handler.index("LLMWorker(self.aura_core, messages,")
        self.assertLess(build_pos, worker_pos)


if __name__ == "__main__":
    unittest.main()
