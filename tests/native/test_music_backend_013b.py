import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication
from aura_native.ui.music_bridge import NativeMusicBridge


class MusicBackend013BTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_queue_next_previous_and_audio_state(self):
        with tempfile.TemporaryDirectory() as root:
            a = Path(root) / "AURA_LOT013B_A.wav"
            b = Path(root) / "AURA_LOT013B_B.wav"
            a.write_bytes(b"RIFF")
            b.write_bytes(b"RIFF")
            bridge = NativeMusicBridge()
            try:
                self.assertTrue(bridge.loadMusic(str(a)))
                self.assertTrue(bridge.loadMusic(str(b)))
                self.assertEqual(bridge.currentTitle, "AURA_LOT013B_B")
                bridge.previous()
                self.assertEqual(bridge.currentTitle, "AURA_LOT013B_A")
                bridge.next()
                self.assertEqual(bridge.currentTitle, "AURA_LOT013B_B")
                bridge.setVolume(25)
                self.assertEqual(bridge.volume, 25)
                bridge.mute()
                self.assertTrue(bridge.muted)
                bridge.unmute()
                self.assertFalse(bridge.muted)
            finally:
                bridge.stop()
                bridge.shutdown()
                bridge._player.deleteLater()
                bridge._audio.deleteLater()
                self.app.processEvents()

    def test_invalid_seek_is_truthful(self):
        bridge = NativeMusicBridge()
        try:
            bridge.seekPercent(50)
            self.assertEqual(bridge._error, "UNKNOWN_DURATION")
        finally:
            bridge.stop()
            bridge.shutdown()
            bridge._player.deleteLater()
            bridge._audio.deleteLater()
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
