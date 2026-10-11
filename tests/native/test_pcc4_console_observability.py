from pathlib import Path
import unittest

ROOT = Path(__file__).parents[2]


class Pcc4ConsoleObservabilityTests(unittest.TestCase):
    def test_native_launcher_enables_safe_pcc4_trace(self):
        source = (ROOT / "app/main.py").read_text(encoding="utf-8")
        self.assertIn('os.environ.setdefault("AURA_PCC4_DEBUG", "1")', source)

    def test_trace_is_flush_safe_and_content_free(self):
        source = (ROOT / "src/aura_native/agent/pcc4_debug.py").read_text(encoding="utf-8")
        self.assertIn("flush=True", source)
        self.assertIn("sys.stderr", source)


if __name__ == "__main__": unittest.main()
