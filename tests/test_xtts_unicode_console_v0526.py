from __future__ import annotations

import io
import unittest
from unittest.mock import patch

from scripts import xtts_safe_probe


class _Cp1252Stream(io.StringIO):
    encoding = "cp1252"

    def write(self, s):
        # Simulate a legacy Windows console that cannot encode dotless i.
        s.encode("cp1252")
        return super().write(s)


class XTTSUnicodeConsoleTests(unittest.TestCase):
    def test_out_never_crashes_on_non_cp1252_speaker_name(self):
        stream = _Cp1252Stream()
        with patch.object(xtts_safe_probe.sys, "stdout", stream):
            xtts_safe_probe.out("Kıvanç Özel")
        self.assertTrue(stream.getvalue())

    def test_bat_launchers_force_utf8(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        for name in ("XTTS_CPU_PROBE.bat", "XTTS_VOICE_DIAGNOSTICS.bat"):
            content = (root / name).read_text(encoding="utf-8")
            self.assertIn("chcp 65001", content)
            self.assertIn("PYTHONIOENCODING=utf-8", content)


if __name__ == "__main__":
    unittest.main()
