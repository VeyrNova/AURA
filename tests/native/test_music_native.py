import tempfile, unittest
from pathlib import Path
from PySide6.QtGui import QGuiApplication
from aura_native.ui.music_bridge import NativeMusicBridge

class MusicNativeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.app=QGuiApplication.instance() or QGuiApplication([])
 def setUp(self): self.bridge=NativeMusicBridge()
 def tearDown(self): self.bridge.shutdown()
 def test_qt_multimedia_bridge_and_invalid_load(self):
  self.assertTrue(self.bridge.available); self.assertFalse(self.bridge.loadMusic('missing-aura-track.mp3')); self.assertEqual(self.bridge.currentId,'')
 def test_load_play_pause_seek_volume(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'sample.wav'; p.write_bytes(b'RIFF'+b'\x00'*32)
   self.assertTrue(self.bridge.loadMusic(str(p))); self.assertEqual(self.bridge.playlistCount,1); self.bridge.setVolume(42); self.assertEqual(self.bridge.volume,42); self.bridge.play(); self.bridge.pause(); self.bridge.seekPercent(50)

if __name__=='__main__': unittest.main()
