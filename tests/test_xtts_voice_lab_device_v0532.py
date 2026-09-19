from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class VoiceLabDeviceReportingTests(unittest.TestCase):
    def test_launcher_does_not_claim_cpu_unconditionally(self):
        text=(ROOT/'XTTS_VOICE_LAB.bat').read_text(encoding='utf-8')
        self.assertNotIn('Chargement du modele XTTS en CPU', text)
        self.assertIn('xtts_runtime_status.py', text)

    def test_runtime_status_tool_exists(self):
        self.assertTrue((ROOT/'scripts'/'xtts_runtime_status.py').is_file())
        self.assertTrue((ROOT/'XTTS_RUNTIME_STATUS.bat').is_file())

if __name__ == '__main__': unittest.main()
